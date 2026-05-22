"""
TranscriptService — business logic for transcript retrieval.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.models.media_file import MediaFile
from app.models.transcript import Transcript
from app.schemas.transcript import TranscriptResponse
from app.services.base_service import BaseService


class TranscriptService(BaseService):
    """
    Encapsulates business logic for Transcript records.

    Enforces ownership by cross-referencing the transcript's media file
    with the requesting user's ID before returning any data.
    """

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_transcript_for_file(
        self,
        file_id: uuid.UUID,
        user_id: str,
    ) -> TranscriptResponse:
        """
        Retrieve the transcript for a specific media file.

        Args:
            file_id: UUID of the parent media file.
            user_id: Requesting user's UUID string (ownership check).

        Returns:
            TranscriptResponse schema.

        Raises:
            NotFoundError:      If no transcript exists for the file, or file not found.
            AuthorizationError: If the requesting user doesn't own the file.
        """
        # Verify the media file exists and belongs to the user
        file_result = await self.db.execute(
            select(MediaFile).where(MediaFile.id == file_id)
        )
        media_file = file_result.scalar_one_or_none()

        if not media_file:
            raise NotFoundError(f"Media file '{file_id}' not found.")

        if str(media_file.user_id) != user_id:
            raise AuthorizationError("You do not have access to this resource.")

        # Fetch the associated transcript
        tx_result = await self.db.execute(
            select(Transcript).where(Transcript.file_id == file_id)
        )
        transcript = tx_result.scalar_one_or_none()

        if not transcript:
            raise NotFoundError(
                f"Transcript not yet available for file '{file_id}'. "
                "Processing may still be in progress."
            )

        self.logger.info(
            "Fetched transcript",
            file_id=str(file_id),
            user_id=user_id,
            text_length=len(transcript.raw_text),
        )
        return TranscriptResponse.model_validate(transcript)

    async def save_transcript(
        self,
        file_id: uuid.UUID,
        raw_text: str,
        segments: list | None,
    ) -> Transcript:
        """
        Persist a new Transcript record (called by workers only).

        Args:
            file_id:  Parent media file UUID.
            raw_text: Full concatenated transcription.
            segments: Structured Whisper segments (optional).

        Returns:
            Newly created Transcript instance.
        """
        transcript = Transcript(
            file_id=file_id,
            raw_text=raw_text,
            segments=segments,
        )
        self.db.add(transcript)
        await self.db.flush()

        self.logger.info(
            "Saved transcript",
            file_id=str(file_id),
            text_length=len(raw_text),
            segment_count=len(segments) if segments else 0,
        )
        return transcript
