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
import uuid
from pathlib import Path

import aiofiles
import aiohttp
import dramatiq
import google.generativeai as genai
from openai import OpenAI

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

openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

genai.configure(api_key=settings.GEMINI_API_KEY)
gemini_model = genai.GenerativeModel(settings.GEMINI_MODEL)

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


def _transcribe_with_whisper(file_path: Path) -> tuple[str, list[dict]]:
    """
    Transcribe an audio file using OpenAI Whisper API.

    Handles large files by splitting into chunks < 25MB (Whisper API limit).

    Returns:
        (raw_text, segments) tuple.
    """
    file_size = file_path.stat().st_size
    chunk_limit = settings.whisper_chunk_size_bytes  # default 20MB

    if file_size <= chunk_limit:
        # Small file — transcribe directly
        with open(file_path, "rb") as audio_file:
            response = openai_client.audio.transcriptions.create(
                model=settings.WHISPER_MODEL,
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )
        segments = [
            {
                "start": s.start,
                "end": s.end,
                "text": s.text.strip(),
                "speaker": None,
            }
            for s in (response.segments or [])
        ]
        return response.text, segments
    else:
        # Large file — split into chunks using pydub
        logger.info(
            "File exceeds Whisper chunk limit, splitting",
            file_size=file_size,
            chunk_limit=chunk_limit,
        )
        return _transcribe_chunked(file_path, chunk_limit)


def _transcribe_chunked(file_path: Path, chunk_size_bytes: int) -> tuple[str, list[dict]]:
    """
    Split a large audio file into chunks and transcribe each segment.

    Uses pydub for audio splitting (requires ffmpeg installed).
    """
    try:
        from pydub import AudioSegment
    except ImportError as exc:
        raise RuntimeError(
            "pydub is required for large file transcription. "
            "Ensure ffmpeg is installed: https://ffmpeg.org/download.html"
        ) from exc

    audio = AudioSegment.from_file(str(file_path))
    duration_ms = len(audio)
    # Approximate ms per chunk based on file size ratio
    chunk_ms = int(duration_ms * (chunk_size_bytes / file_path.stat().st_size))
    chunk_ms = max(chunk_ms, 60_000)  # minimum 1-minute chunks

    all_text_parts: list[str] = []
    all_segments: list[dict] = []
    time_offset = 0.0

    chunk_idx = 0
    for start_ms in range(0, duration_ms, chunk_ms):
        end_ms = min(start_ms + chunk_ms, duration_ms)
        chunk = audio[start_ms:end_ms]

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name
            chunk.export(tmp_path, format="mp3")

        try:
            with open(tmp_path, "rb") as audio_file:
                response = openai_client.audio.transcriptions.create(
                    model=settings.WHISPER_MODEL,
                    file=audio_file,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                )

            all_text_parts.append(response.text)
            for s in (response.segments or []):
                all_segments.append({
                    "start": round(s.start + time_offset, 3),
                    "end": round(s.end + time_offset, 3),
                    "text": s.text.strip(),
                    "speaker": None,
                })

            time_offset += (end_ms - start_ms) / 1000.0
        finally:
            os.unlink(tmp_path)

        chunk_idx += 1
        logger.info("Transcribed chunk", chunk=chunk_idx, start_ms=start_ms, end_ms=end_ms)

    return " ".join(all_text_parts), all_segments


def _generate_gemini_summary(raw_text: str) -> dict:
    """
    Generate structured summary using Google Gemini Flash.

    Returns a dict with keys: executive_summary, key_takeaways, action_items.
    """
    # Truncate extremely long transcripts to fit in context window
    max_chars = 500_000  # ~125k tokens for Gemini Flash
    truncated = raw_text[:max_chars] if len(raw_text) > max_chars else raw_text

    prompt = _GEMINI_SUMMARY_PROMPT.format(transcript=truncated)

    response = gemini_model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
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

            # ── 6. Transcribe with Whisper ────────────────────────────────────
            logger.info("Starting Whisper transcription", file_id=file_id)
            raw_text, segments = _transcribe_with_whisper(tmp_file)
            logger.info(
                "Transcription complete",
                file_id=file_id,
                char_count=len(raw_text),
                segment_count=len(segments),
            )

            # ── 7. Summarize with Gemini Flash ────────────────────────────────
            logger.info("Starting Gemini summarization", file_id=file_id)
            summary_data = _generate_gemini_summary(raw_text)
            logger.info("Summarization complete", file_id=file_id)

            # ── 8. Atomically save Transcript + Summary ───────────────────────
            transcript = Transcript(
                file_id=fid,
                raw_text=raw_text,
                segments=segments if segments else None,
            )
            db.add(transcript)

            summary = Summary(
                file_id=fid,
                executive_summary=summary_data["executive_summary"],
                key_takeaways=summary_data.get("key_takeaways", []),
                action_items=summary_data.get("action_items", []),
            )
            db.add(summary)

            # ── 9. Mark as completed ──────────────────────────────────────────
            media_file.status = FileStatus.COMPLETED
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
                tmp_file.unlink()
                logger.info("Cleaned up temp file", path=str(tmp_file))
