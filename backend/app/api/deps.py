"""
FastAPI dependency functions — shared across all API route handlers.

Provides:
- `get_db`: Async database session
- `get_current_user`: JWT-authenticated CurrentUser
- `get_media_service`: Injected MediaService
- `get_transcript_service`: Injected TranscriptService
- `get_summary_service`: Injected SummaryService
"""

from __future__ import annotations

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, extract_bearer_token, verify_supabase_jwt
from app.database import get_db
from app.services.media_service import MediaService
from app.services.storage_service import StorageService, get_storage_service
from app.services.summary_service import SummaryService
from app.services.transcript_service import TranscriptService


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> CurrentUser:
    """
    FastAPI dependency that validates the Supabase JWT from the Authorization header.

    Raises HTTP 401 if the token is missing, expired, or invalid.
    """
    token = extract_bearer_token(authorization)
    return verify_supabase_jwt(token)


async def get_media_service(
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> MediaService:
    """Provide a fully-wired MediaService instance."""
    return MediaService(db=db, storage=storage)


async def get_transcript_service(
    db: AsyncSession = Depends(get_db),
) -> TranscriptService:
    """Provide a fully-wired TranscriptService instance."""
    return TranscriptService(db=db)


async def get_summary_service(
    db: AsyncSession = Depends(get_db),
) -> SummaryService:
    """Provide a fully-wired SummaryService instance."""
    return SummaryService(db=db)
