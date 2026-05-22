"""
Abstract base service class.

All service classes inherit from BaseService which provides a shared
async DB session and a structured logger bound with the service name.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger


class BaseService:
    """
    Abstract base for all EchoBrief service classes.

    Services encapsulate business logic and act as the bridge between
    API route handlers and the database/external services layer.

    Usage:
        class MediaService(BaseService):
            async def do_something(self) -> ...:
                result = await self.db.execute(...)
                return result
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialise the service with an injected async database session.

        Args:
            db: SQLAlchemy async session provided by FastAPI's dependency
                injection system via `get_db`.
        """
        self.db = db
        self.logger = get_logger(self.__class__.__name__)
