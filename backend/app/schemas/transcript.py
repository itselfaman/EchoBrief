"""
Pydantic schemas for Transcript API endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    """A single timed segment from the ASR output."""

    start: float = Field(..., description="Segment start time in seconds")
    end: float = Field(..., description="Segment end time in seconds")
    text: str = Field(..., description="Transcribed text for this segment")
    speaker: str | None = Field(None, description="Speaker label (e.g. SPEAKER_00)")


class TranscriptResponse(BaseModel):
    """Full transcript returned by the API."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    file_id: uuid.UUID
    raw_text: str
    segments: list[Any] | None
    created_at: datetime
