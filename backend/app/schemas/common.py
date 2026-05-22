"""
Common Pydantic schemas used across multiple API endpoints.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated list response wrapper."""

    items: list[T]
    total: int = Field(..., description="Total number of records matching the query")
    page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    per_page: int = Field(..., ge=1, le=100, description="Items per page")
    pages: int = Field(..., description="Total number of pages")


class MessageResponse(BaseModel):
    """Simple message-only response."""

    message: str


class ErrorDetail(BaseModel):
    """Structured error detail for API error responses."""

    code: str
    message: str
    field: str | None = None


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    error: ErrorDetail
