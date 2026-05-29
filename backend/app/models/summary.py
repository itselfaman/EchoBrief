"""
Summary ORM model — stores LLM-generated structured insights for a media file.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, func, Float
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Summary(Base):
    """
    Stores structured AI-generated analysis produced by the Gemini worker.

    Has a strict 1:1 relationship with MediaFile enforced at the DB level.

    JSONB structures:
    - key_takeaways: [{"point": "...", "category": "insight|decision|risk"}]
    - action_items:  [{"task": "...", "owner": "...", "priority": "high|medium|low"}]
    """

    __tablename__ = "summaries"
    __table_args__ = (
        UniqueConstraint("file_id", name="uq_summaries_file_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
        comment="Unique summary row identifier",
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("media_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="References the parent media asset",
    )
    executive_summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="3-5 paragraph narrative summary synthesized by Gemini",
    )
    key_takeaways: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        comment='Structured insights: [{"point": "...", "category": "..."}]',
    )
    action_items: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        comment='Action items: [{"task": "...", "owner": "...", "priority": "..."}]',
    )
    generation_time_sec: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Time in seconds taken to generate the summary",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="LLM synthesis completion timestamp",
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    media_file: Mapped["MediaFile"] = relationship(  # type: ignore[name-defined]
        "MediaFile",
        back_populates="summary",
        lazy="select",
    )

    def __repr__(self) -> str:
        preview = (self.executive_summary or "")[:60].replace("\n", " ")
        return f"<Summary file_id={self.file_id!s} preview={preview!r}>"
