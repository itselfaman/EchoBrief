"""
EchoBrief FastAPI Application Entry Point.

Configures:
- Lifespan (startup/shutdown) — DB pool warmup, temp dir creation
- CORS middleware
- Rate limiting (slowapi)
- Global exception handlers (domain errors → structured JSON)
- Request ID middleware
- All API v1 routers
- OpenAPI metadata
- Health check endpoint
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.v1.router import v1_router
from app.config import settings
from app.core.exceptions import EchoBriefError
from app.core.logging import configure_logging
from app.database import engine

# Configure structured logging before anything else
configure_logging()

logger = structlog.get_logger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Startup:
    - Warm up the database connection pool
    - Create temp media directory

    Shutdown:
    - Dispose of the DB engine
    """
    logger.info(
        "Starting EchoBrief API",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )

    # Create temp directory for worker downloads
    Path(settings.TEMP_MEDIA_DIR).mkdir(parents=True, exist_ok=True)

    # Warm up DB pool
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: None)
    logger.info("Database connection pool warmed up")

    yield

    # Shutdown
    await engine.dispose()
    logger.info("EchoBrief API shut down cleanly")


# ── Rate Limiter ──────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)


# ── App Factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "EchoBrief — AI-Powered Asynchronous Media Transcription & Summarization Hub. "
            "Upload audio/video files to receive AI-generated transcripts, executive summaries, "
            "key takeaways, and action items."
        ),
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── State ──────────────────────────────────────────────────────────────────
    app.state.limiter = limiter

    # ── Middleware ─────────────────────────────────────────────────────────────

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time"],
    )

    # ── Request ID & Timing Middleware ─────────────────────────────────────────
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next) -> Response:
        """Attach a unique request ID and process-time header to every response."""
        request_id = str(uuid.uuid4())
        start_time = time.monotonic()

        # Bind context for all log statements within this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        response = await call_next(request)

        process_time_ms = round((time.monotonic() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time_ms}ms"

        logger.info(
            "Request completed",
            status_code=response.status_code,
            duration_ms=process_time_ms,
        )
        return response

    # ── Exception Handlers ─────────────────────────────────────────────────────

    @app.exception_handler(EchoBriefError)
    async def echobrief_error_handler(request: Request, exc: EchoBriefError) -> JSONResponse:
        """Convert domain errors to structured JSON responses."""
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "field": exc.field,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Format Pydantic validation errors consistently."""
        errors = exc.errors()
        first = errors[0] if errors else {}
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": first.get("msg", "Validation failed"),
                    "field": ".".join(str(l) for l in first.get("loc", [])),
                    "details": errors,
                }
            },
        )

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        """Return a structured error for rate limit violations."""
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests. Please slow down.",
                    "field": None,
                }
            },
        )

    # ── Routers ────────────────────────────────────────────────────────────────

    app.include_router(v1_router, prefix=settings.API_V1_PREFIX)

    # ── Health Check ───────────────────────────────────────────────────────────

    @app.get("/health", tags=["Health"], include_in_schema=True)
    async def health_check() -> dict:
        """Liveness probe endpoint — returns 200 when the service is running."""
        return {
            "status": "healthy",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
        }

    return app


# ── WSGI App Instance ─────────────────────────────────────────────────────────

app = create_app()
