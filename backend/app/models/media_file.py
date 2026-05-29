"""
MediaFile ORM model — tracks uploaded media assets and their processing state.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, Text, Float, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class FileStatus(str, enum.Enum):
    """
    Finite state machine for media file processing lifecycle.

    Transitions:
      pending → processing → completed
                           → failed
    """

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        """Return True if this status is a final (non-retryable) state."""
        return self in (FileStatus.COMPLETED, FileStatus.FAILED)


class MediaFile(Base):
    """
    Represents a single uploaded media asset and its entire processing lifecycle.

    Uploading, transcribing, and summarizing are tracked via the `status` column.
    Workers check `status` before processing to ensure idempotency.
    """

    __tablename__ = "media_files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
        comment="Unique tracking identifier for the media asset",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owner user ID — references users.id",
    )
    file_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Original filename as provided by the client",
    )
    storage_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Supabase Storage bucket path (e.g. user_id/uuid/filename.mp3)",
    )
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Raw file size in bytes — used for subscription enforcement",
    )
    status: Mapped[FileStatus] = mapped_column(
        Enum(
            FileStatus,
            name="file_status_enum",
            create_type=True,
            values_callable=lambda obj: [e.value for e in obj]
        ),
        nullable=False,
        default=FileStatus.PENDING,
        server_default=FileStatus.PENDING.value,
        index=True,
        comment="Processing lifecycle state",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Failure reason stored when status transitions to 'failed'",
    )
    processing_message: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Current processing progress state description",
    )
    audio_duration_seconds: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Duration of the audio file in seconds",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Upload initialization timestamp",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Last state update timestamp",
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    owner: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User",
        back_populates="media_files",
        lazy="select",
    )
    transcript: Mapped["Transcript | None"] = relationship(  # type: ignore[name-defined]
        "Transcript",
        back_populates="media_file",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="select",
    )
    summary: Mapped["Summary | None"] = relationship(  # type: ignore[name-defined]
        "Summary",
        back_populates="media_file",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<MediaFile id={self.id!s} name={self.file_name!r} status={self.status.value!r}>"
        )
