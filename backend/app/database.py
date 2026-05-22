"""
Async SQLAlchemy database engine and session factory.

Provides:
- Async engine connected to PostgreSQL via asyncpg
- Async session factory (AsyncSessionLocal)
- `get_db` dependency for FastAPI routes
- `Base` declarative model class (imported from models.base)
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import settings

# ── Engine ────────────────────────────────────────────────────────────────────

# NullPool is used to avoid connection pool issues with asyncpg in multi-process
# worker environments (Dramatiq). The API process uses a standard pool.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,           # log SQL in debug mode
    pool_pre_ping=True,            # verify connections before checkout
    pool_size=10,                  # max persistent connections
    max_overflow=20,               # extra connections under load
    pool_recycle=3600,             # recycle connections every hour
    pool_timeout=30,               # wait up to 30s for a free connection
    connect_args={
        "server_settings": {
            "application_name": settings.APP_NAME,
        },
        "command_timeout": 60,
    },
)

# Separate engine for Dramatiq workers — no connection pooling across processes
worker_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

# ── Session Factory ───────────────────────────────────────────────────────────

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # prevents lazy-loading after commit
    autocommit=False,
    autoflush=False,
)

WorkerAsyncSessionLocal = async_sessionmaker(
    bind=worker_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ── Dependency ────────────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a managed database session.

    Automatically commits on success and rolls back on exception.
    Always closes the session when the request ends.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_worker_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for Dramatiq workers — uses NullPool engine.
    """
    async with WorkerAsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
