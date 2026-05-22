"""Transcript API endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_transcript_service
from app.core.security import CurrentUser
from app.schemas.transcript import TranscriptResponse
from app.services.transcript_service import TranscriptService

router = APIRouter(prefix="/media", tags=["Transcripts"])


@router.get(
    "/{file_id}/transcript",
    response_model=TranscriptResponse,
    summary="Retrieve the transcript for a media file",
    description=(
        "Returns the full raw transcript text and structured segments. "
        "Returns 404 if the file is still processing."
    ),
)
async def get_transcript(
    file_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TranscriptService = Depends(get_transcript_service),
) -> TranscriptResponse:
    """Fetch the ASR-generated transcript for a completed media file."""
    return await service.get_transcript_for_file(file_id, current_user.user_id)
