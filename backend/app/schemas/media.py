"""
Pydantic schemas for MediaFile API endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.media_file import FileStatus


class MediaUploadRequest(BaseModel):
    """
    Request body for POST /api/v1/media/upload.

    The client uploads the binary file directly to Supabase Storage,
    then sends this metadata payload to the FastAPI backend.
    """

    file_name: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Original filename including extension",
        examples=["team_standup_2024-01-15.mp3"],
    )
    storage_path: str = Field(
        ...,
        min_length=1,
        description="Full Supabase Storage path (e.g. user_id/uuid/filename.mp3)",
        examples=["a1b2c3/7d8e9f/team_standup_2024-01-15.mp3"],
    )
    file_size_bytes: int = Field(
        ...,
        gt=0,
        description="File size in bytes — must be > 0",
    )
    mime_type: str = Field(
        ...,
        description="MIME type of the uploaded file",
        examples=["audio/mpeg"],
    )

    @field_validator("file_name")
    @classmethod
    def sanitize_file_name(cls, v: str) -> str:
        """Strip directory traversal characters from filenames."""
        return v.replace("..", "").replace("/", "").replace("\\", "").strip()


class MediaUploadResponse(BaseModel):
    """Response for a successfully queued upload."""

    message: str
    file_id: uuid.UUID


class MediaFileResponse(BaseModel):
    """Full media file representation returned by the API."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    file_name: str
    storage_path: str
    file_size_bytes: int
    status: FileStatus
    error_message: str | None
    processing_message: str | None
    audio_duration_seconds: float | None
    created_at: datetime
    updated_at: datetime


class MediaFileListResponse(BaseModel):
    """Paginated list of media files."""

    items: list[MediaFileResponse]
    total: int
    page: int
    per_page: int
    pages: int
