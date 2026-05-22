"""
User ORM model — synced from Supabase auth via webhook/trigger.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    """
    Represents an authenticated user whose identity is managed by Supabase Auth.

    The `id` must match the corresponding `auth.users.id` in Supabase so that
    Row-Level Security policies and foreign key relationships work correctly.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        comment="UUID matching Supabase auth.users.id",
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="User's authenticated email address",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Account profile creation timestamp",
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    media_files: Mapped[list["MediaFile"]] = relationship(  # type: ignore[name-defined]
        "MediaFile",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id!s} email={self.email!r}>"
