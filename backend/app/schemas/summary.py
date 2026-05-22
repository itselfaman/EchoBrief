"""
Pydantic schemas for Summary API endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class KeyTakeaway(BaseModel):
    """A single structured key insight from the meeting/recording."""

    point: str = Field(..., description="The insight text")
    category: Literal["insight", "decision", "risk", "opportunity"] = Field(
        "insight",
        description="Classification of the takeaway",
    )


class ActionItem(BaseModel):
    """A single actionable task extracted from the recording."""

    task: str = Field(..., description="Description of the action required")
    owner: str | None = Field(None, description="Person responsible (if mentioned)")
    priority: Literal["high", "medium", "low"] = Field(
        "medium",
        description="Urgency level inferred from context",
    )


class SummaryResponse(BaseModel):
    """Full summary returned by the API."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    file_id: uuid.UUID
    executive_summary: str
    key_takeaways: list[KeyTakeaway]
    action_items: list[ActionItem]
    created_at: datetime
