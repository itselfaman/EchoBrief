"""
ORM model registry — import all models here so that:
1. Alembic autogenerate detects them
2. SQLAlchemy relationship resolution works correctly
"""

from app.models.base import Base
from app.models.media_file import FileStatus, MediaFile
from app.models.summary import Summary
from app.models.transcript import Transcript
from app.models.user import User

__all__ = [
    "Base",
    "User",
    "MediaFile",
    "FileStatus",
    "Transcript",
    "Summary",
]
