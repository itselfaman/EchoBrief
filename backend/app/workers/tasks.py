"""
Dramatiq worker tasks — the core of EchoBrief's async processing pipeline.

Pipeline for each media file:
  1. Idempotency check (skip if already completed)
  2. Update status → 'processing'
  3. Generate signed download URL from Supabase Storage
  4. Download file to temp directory
  5. Transcribe using OpenAI Whisper API (with chunking for large files)
  6. Summarize using Google Gemini Flash (structured JSON output)
  7. Atomically save Transcript + Summary records
  8. Update status → 'completed'

On any unhandled exception:
  - Update status → 'failed' with error_message
  - Dramatiq retries up to DRAMATIQ_MAX_RETRIES times
  - After max retries, task goes to Dead Letter Queue
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
import uuid
from pathlib import Path

import aiofiles
import aiohttp
import dramatiq
from google import genai
from google.genai import types as genai_types
import ollama

from app.config import settings
from app.core.logging import get_logger
from app.database import WorkerAsyncSessionLocal
from app.models.media_file import FileStatus, MediaFile
from app.models.summary import Summary
from app.models.transcript import Transcript
from app.services.storage_service import StorageService
from app.workers.broker import redis_broker  # noqa: F401 — ensures broker is configured

logger = get_logger(__name__)

# ── AI Clients ────────────────────────────────────────────────────────────────

gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)

_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        logger.info("Loading faster-whisper model...")
        # Using base model, compute_type=int8 for best CPU performance on Windows
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    return _whisper_model

# ── Helpers ───────────────────────────────────────────────────────────────────

_GEMINI_SUMMARY_PROMPT = """
You are an expert meeting analyst. Analyze the following audio transcript and produce a structured JSON response.

TRANSCRIPT:
{transcript}

Respond with ONLY valid JSON (no markdown, no extra text) in this exact structure:
{{
  "executive_summary": "A comprehensive 3-5 paragraph narrative covering the main discussion, key decisions, and overall context...",
  "key_takeaways": [
    {{"point": "Specific insight or conclusion", "category": "insight"}},
    {{"point": "A decision that was made", "category": "decision"}},
    {{"point": "A potential risk identified", "category": "risk"}},
    {{"point": "An opportunity discussed", "category": "opportunity"}}
  ],
  "action_items": [
    {{"task": "Specific action to take", "owner": "Person name or null", "priority": "high"}},
    {{"task": "Another action item", "owner": null, "priority": "medium"}}
  ]
}}

Generate at least 3 key_takeaways and include all action items mentioned. Use null for owner if not explicitly mentioned.
"""


async def _download_file(url: str, destination: Path) -> None:
    """Stream-download a file from a URL to a local path."""
    destination.parent.mkdir(parents=True, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            async with aiofiles.open(destination, mode="wb") as f:
                async for chunk in response.content.iter_chunked(8 * 1024 * 1024):  # 8MB chunks
                    await f.write(chunk)

    logger.info(
        "Downloaded media file",
        destination=str(destination),
        size_bytes=destination.stat().st_size,
    )


def _transcribe_with_faster_whisper(file_path: Path) -> tuple[str, list[dict], float]:
    """
    Transcribe an audio file using local faster-whisper model.
    """
    model = get_whisper_model()
    
    try:
        # We do not need to chunk manually since faster-whisper handles long audio via VAD/chunking internally
        segments_generator, info = model.transcribe(str(file_path), beam_size=5, word_timestamps=False)
    except IndexError as exc:
        # faster-whisper raises IndexError (with an empty or any message) when the file
        # has no detectable audio track. Catch any IndexError from this call and surface
        # it as a clear user-facing ValueError.
        logger.error(
            "No audio track found in the media file",
            file_path=str(file_path),
            error=str(exc) or "(no message — likely empty audio track)",
        )
        raise ValueError("No audio track detected in the uploaded file.") from exc
    
    all_text_parts = []
    all_segments = []
    
    for segment in segments_generator:
        all_text_parts.append(segment.text.strip())
        all_segments.append({
            "start": round(segment.start, 3),
            "end": round(segment.end, 3),
            "text": segment.text.strip(),
            "speaker": None,
        })
        
    return " ".join(all_text_parts), all_segments, info.duration


def _generate_gemini_summary(raw_text: str) -> dict:
    """
    Generate structured summary using Google Gemini Flash.

    Returns a dict with keys: executive_summary, key_takeaways, action_items.
    """
    # Truncate extremely long transcripts to fit in context window
    max_chars = 500_000  # ~125k tokens for Gemini Flash
    truncated = raw_text[:max_chars] if len(raw_text) > max_chars else raw_text

    prompt = _GEMINI_SUMMARY_PROMPT.format(transcript=truncated)

    try:
        response = gemini_client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=8192,
            ),
        )

        content = response.text.strip()

        # Strip markdown code fences if Gemini wraps the JSON
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        return json.loads(content)
    except Exception as exc:
        logger.warning("Gemini API failed, falling back to Ollama.", error=str(exc))
        return _generate_ollama_summary(raw_text)

def _generate_ollama_summary(raw_text: str) -> dict:
    """
    Generate structured summary using local Ollama model (llama3.2).
    """
    max_chars = 100_000  # Local models usually have smaller context window (8k-128k)
    truncated = raw_text[:max_chars] if len(raw_text) > max_chars else raw_text

    prompt = _GEMINI_SUMMARY_PROMPT.format(transcript=truncated)
    
    logger.info("Calling local Ollama API (llama3.2)...")
    try:
        response = ollama.generate(
            model="llama3.2",
            prompt=prompt,
            format="json",
            options={"temperature": 0.3}
        )
        content = response["response"].strip()
        return json.loads(content)
    except Exception as exc:
        logger.error("Ollama fallback failed", error=str(exc))
        raise RuntimeError("Both Gemini and Ollama fallback failed to summarize.") from exc


# ── Dramatiq Actor ────────────────────────────────────────────────────────────

@dramatiq.actor(
    max_retries=settings.DRAMATIQ_MAX_RETRIES,
    time_limit=7_200_000,   # 2 hours (for very large files)
    queue_name="echobrief_processing",
)
def process_media_task(file_id: str) -> None:
    """
    Main Dramatiq actor: orchestrates the full transcription + summarization pipeline.

    Args:
        file_id: String UUID of the MediaFile record to process.
    """
    asyncio.run(_process_media_async(file_id))


async def _process_media_async(file_id: str) -> None:
    """Async implementation of the media processing pipeline."""
    fid = uuid.UUID(file_id)
    logger.info("Starting media processing", file_id=file_id)

    async with WorkerAsyncSessionLocal() as db:
        # ── 1. Fetch the media file record ────────────────────────────────────
        from sqlalchemy import select
        result = await db.execute(select(MediaFile).where(MediaFile.id == fid))
        media_file = result.scalar_one_or_none()

        if not media_file:
            logger.error("Media file not found", file_id=file_id)
            return

        # ── 2. Idempotency check ──────────────────────────────────────────────
        if media_file.status.is_terminal:
            logger.info(
                "Skipping already-terminal file",
                file_id=file_id,
                status=media_file.status.value,
            )
            return

        # ── 3. Transition to 'processing' ─────────────────────────────────────
        media_file.status = FileStatus.PROCESSING
        await db.commit()

        tmp_file: Path | None = None
        try:
            # ── 4. Get signed download URL ─────────────────────────────────────
            media_file.processing_message = "Downloading media..."
            await db.commit()
            
            storage = StorageService()
            signed_url = storage.get_signed_download_url(
                media_file.storage_path,
                expires_in=7200,
            )

            # ── 5. Download file to temp directory ────────────────────────────
            tmp_dir = Path(settings.TEMP_MEDIA_DIR)
            tmp_dir.mkdir(parents=True, exist_ok=True)

            suffix = Path(media_file.file_name).suffix or ".mp3"
            tmp_file = tmp_dir / f"{file_id}{suffix}"

            await _download_file(signed_url, tmp_file)

            # ── 6. Transcribe with local faster-whisper ───────────────────────
            media_file.processing_message = "Transcribing audio..."
            await db.commit()
            logger.info("Starting local Whisper transcription", file_id=file_id)
            raw_text, segments, duration = _transcribe_with_faster_whisper(tmp_file)
            media_file.audio_duration_seconds = duration
            logger.info(
                "Transcription complete",
                file_id=file_id,
                char_count=len(raw_text),
                segment_count=len(segments),
            )

            # ── 7. Summarize with Gemini Flash / Ollama ────────────────────────
            media_file.processing_message = "Generating summary..."
            await db.commit()
            logger.info("Starting summarization", file_id=file_id)
            start_time = time.monotonic()
            # Threshold set to 50 to avoid Whisper hallucinated short segments (e.g. "Thank you.")
            if len(raw_text.strip()) < 50:
                logger.info("Transcript is empty or below minimum character threshold. Skipping summarization.", file_id=file_id)
                summary_data = {
                    "executive_summary": "No speech detected in the uploaded audio.",
                    "key_takeaways": [],
                    "action_items": []
                }
            else:
                summary_data = _generate_gemini_summary(raw_text)
            
            generation_time = time.monotonic() - start_time
            logger.info("Summarization complete", file_id=file_id)

            # ── 8. Atomically save Transcript + Summary ───────────────────────
            transcript = Transcript(
                file_id=fid,
                raw_text=raw_text,
                segments=segments if segments else None,
                word_count=len(raw_text.split()),
            )
            db.add(transcript)

            summary = Summary(
                file_id=fid,
                executive_summary=summary_data["executive_summary"],
                key_takeaways=summary_data.get("key_takeaways", []),
                action_items=summary_data.get("action_items", []),
                generation_time_sec=round(generation_time, 2),
            )
            db.add(summary)

            # ── 9. Mark as completed ──────────────────────────────────────────
            media_file.status = FileStatus.COMPLETED
            media_file.processing_message = None
            media_file.error_message = None

            await db.commit()

            logger.info(
                "Media processing completed successfully",
                file_id=file_id,
                transcript_length=len(raw_text),
            )

        except Exception as exc:
            # ── Failure: mark as failed with error details ─────────────────────
            logger.exception("Media processing failed", file_id=file_id, error=str(exc))
            try:
                await db.rollback()
                media_file.status = FileStatus.FAILED
                media_file.error_message = f"{type(exc).__name__}: {str(exc)[:500]}"
                await db.commit()
            except Exception as db_exc:
                logger.error(
                    "Failed to update failure status in DB",
                    file_id=file_id,
                    error=str(db_exc),
                )
            raise  # Re-raise so Dramatiq can retry

        finally:
            # ── Cleanup temp files ─────────────────────────────────────────────
            if tmp_file and tmp_file.exists():
                try:
                    tmp_file.unlink()
                    logger.info("Cleaned up temp file", path=str(tmp_file))
                except Exception as e:
                    logger.warning("Failed to clean up temp file", path=str(tmp_file), error=str(e))
