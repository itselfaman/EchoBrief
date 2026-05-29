"""
Application configuration management using Pydantic Settings.

All settings are loaded from environment variables (or .env file).
Use `get_settings()` to access the singleton settings object.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_list_field(value: Any, default: list[str]) -> list[str]:
    """Parse a list field that may come in as a comma-separated string, JSON array string, or list."""
    if isinstance(value, list):
        return [str(v).strip() for v in value]
    if isinstance(value, str):
        v = value.strip()
        if v.startswith("["):
            import json
            return json.loads(v)
        return [o.strip() for o in v.split(",") if o.strip()]
    return default


class Settings(BaseSettings):
    """
    Centralised application settings loaded from environment variables.

    All fields are validated at startup — missing required values cause
    an immediate startup failure with a clear error message.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = "EchoBrief"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # ── API ───────────────────────────────────────────────────────────────────
    API_V1_PREFIX: str = "/api/v1"
    # Stored internally as Any so pydantic-settings does NOT try to JSON-decode
    # the comma-separated env string. Converted to list[str] by model_validator.
    ALLOWED_ORIGINS: Any = None

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str  # required — postgresql+asyncpg://...

    # ── Supabase ─────────────────────────────────────────────────────────────
    SUPABASE_URL: str  # required
    SUPABASE_ANON_KEY: str  # required
    SUPABASE_SERVICE_ROLE_KEY: str  # required
    SUPABASE_JWT_SECRET: str  # required — used to verify HS256 JWTs
    SUPABASE_STORAGE_BUCKET: str = "media-files"

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None

    # ── OpenAI (Whisper) ─────────────────────────────────────────────────────
    OPENAI_API_KEY: str  # required
    WHISPER_MODEL: str = "whisper-1"
    WHISPER_CHUNK_SIZE_MB: int = 20  # split files larger than this for Whisper API

    # ── Google Gemini (Summarization) ─────────────────────────────────────────
    GEMINI_API_KEY: str  # required
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # ── File Upload Limits ────────────────────────────────────────────────────
    MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB
    ALLOWED_MIME_TYPES: Any = None  # same pattern as ALLOWED_ORIGINS

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_UPLOADS_PER_MINUTE: int = 10

    # ── Worker Config ─────────────────────────────────────────────────────────
    DRAMATIQ_MAX_RETRIES: int = 3
    TEMP_MEDIA_DIR: str = "C:/temp/echobrief"

    # ── Derived Properties ────────────────────────────────────────────────────

    @property
    def redis_url(self) -> str:
        """Construct Redis connection URL from components."""
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def is_production(self) -> bool:
        """True when running in a production environment."""
        return self.ENVIRONMENT.lower() == "production"

    @property
    def whisper_chunk_size_bytes(self) -> int:
        """Whisper API chunk size in bytes."""
        return self.WHISPER_CHUNK_SIZE_MB * 1024 * 1024

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure the database URL uses the asyncpg driver."""
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must use the asyncpg driver: "
                "postgresql+asyncpg://user:pass@host:port/db"
            )
        return v

    @field_validator("SUPABASE_URL")
    @classmethod
    def validate_supabase_url(cls, v: str) -> str:
        """Ensure Supabase URL is a valid HTTPS URL."""
        if not v.startswith("https://"):
            raise ValueError("SUPABASE_URL must be an HTTPS URL.")
        return v.rstrip("/")

    _DEFAULT_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    _DEFAULT_MIME_TYPES: list[str] = [
        "audio/mpeg", "audio/mp4", "audio/wav", "audio/ogg", "audio/flac",
        "audio/x-m4a", "audio/webm", "audio/aac",
        "video/mp4", "video/mpeg", "video/webm", "video/quicktime",
        "video/x-msvideo", "video/x-matroska", "video/3gpp",
    ]

    @model_validator(mode="before")
    @classmethod
    def expand_list_fields(cls, values: Any) -> Any:
        """Parse comma-separated or JSON-array list fields from env variables."""
        if isinstance(values, dict):
            defaults_origins = [
                "http://localhost:5173",
                "http://localhost:3000",
            ]
            defaults_mime = [
                "audio/mpeg", "audio/mp4", "audio/wav", "audio/ogg", "audio/flac",
                "audio/x-m4a", "audio/webm", "audio/aac",
                "video/mp4", "video/mpeg", "video/webm", "video/quicktime",
                "video/x-msvideo", "video/x-matroska", "video/3gpp",
            ]
            values["ALLOWED_ORIGINS"] = _parse_list_field(
                values.get("ALLOWED_ORIGINS"), defaults_origins
            )
            values["ALLOWED_MIME_TYPES"] = _parse_list_field(
                values.get("ALLOWED_MIME_TYPES"), defaults_mime
            )
        return values


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached application settings singleton.

    Uses lru_cache so the .env file is only read once at startup.
    """
    return Settings()


# Module-level convenience alias
settings = get_settings()
