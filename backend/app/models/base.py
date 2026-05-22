"""
SQLAlchemy declarative base for all ORM models.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.

    Provides automatic `created_at` and `updated_at` timestamp columns
    for all inheriting models.
    """

    # Subclasses can optionally opt out of auto-timestamps by overriding these
    __abstract__ = True

    def to_dict(self) -> dict:
        """Return a plain dict representation of this model instance."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
