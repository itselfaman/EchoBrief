"""
Custom exception hierarchy for EchoBrief.

Centralises all domain errors and maps them to appropriate HTTP status codes.
FastAPI exception handlers in main.py catch these and return structured JSON.
"""

from __future__ import annotations

from fastapi import status


class EchoBriefError(Exception):
    """Base class for all EchoBrief application errors."""

    http_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field = field


class AuthenticationError(EchoBriefError):
    """Raised when JWT validation fails or credentials are missing."""

    http_status = status.HTTP_401_UNAUTHORIZED
    error_code = "AUTHENTICATION_ERROR"


class AuthorizationError(EchoBriefError):
    """Raised when a user accesses a resource they don't own."""

    http_status = status.HTTP_403_FORBIDDEN
    error_code = "AUTHORIZATION_ERROR"


class NotFoundError(EchoBriefError):
    """Raised when a requested resource does not exist."""

    http_status = status.HTTP_404_NOT_FOUND
    error_code = "NOT_FOUND"


class ValidationError(EchoBriefError):
    """Raised for business-rule validation failures (beyond Pydantic)."""

    http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "VALIDATION_ERROR"


class FileSizeExceededError(ValidationError):
    """Raised when an uploaded file exceeds the maximum allowed size."""

    error_code = "FILE_SIZE_EXCEEDED"


class UnsupportedMediaTypeError(ValidationError):
    """Raised when the uploaded file's MIME type is not allowed."""

    error_code = "UNSUPPORTED_MEDIA_TYPE"


class ConflictError(EchoBriefError):
    """Raised when an operation conflicts with existing state."""

    http_status = status.HTTP_409_CONFLICT
    error_code = "CONFLICT"


class ServiceUnavailableError(EchoBriefError):
    """Raised when an external service (OpenAI, Gemini) is unavailable."""

    http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "SERVICE_UNAVAILABLE"


class ProcessingError(EchoBriefError):
    """Raised when media processing fails in a worker."""

    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "PROCESSING_ERROR"
