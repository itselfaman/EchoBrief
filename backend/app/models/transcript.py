"""
Transcript ORM model — stores full ASR output for a media file.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Transcript(Base):
    """
    Stores the full speech-to-text output produced by the Whisper worker.

    Has a strict 1:1 relationship with MediaFile enforced at the DB level
    via a UNIQUE constraint on `file_id`.

    The `segments` JSONB column holds structured output:
    [{"start": 0.0, "end": 5.2, "text": "...", "speaker": "SPEAKER_00"}]
    """

    __tablename__ = "transcripts"
    __table_args__ = (
        UniqueConstraint("file_id", name="uq_transcripts_file_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
        comment="Unique transcript row identifier",
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("media_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="References the parent media asset",
    )
    raw_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full concatenated transcription text",
    )
    segments: Mapped[dict | list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Structured segments: [{start, end, text, speaker}]",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Worker completion timestamp",
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    media_file: Mapped["MediaFile"] = relationship(  # type: ignore[name-defined]
        "MediaFile",
        back_populates="transcript",
        lazy="select",
    )

    def __repr__(self) -> str:
        preview = (self.raw_text or "")[:60].replace("\n", " ")
        return f"<Transcript file_id={self.file_id!s} preview={preview!r}>"
