"""Summary API endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_current_user, get_summary_service
from app.core.rate_limit import limiter
from app.core.security import CurrentUser
from app.schemas.summary import SummaryResponse
from app.services.summary_service import SummaryService

router = APIRouter(prefix="/media", tags=["Summaries"])


@router.get(
    "/{file_id}/summary",
    response_model=SummaryResponse,
    summary="Retrieve the AI-generated summary for a media file",
    description=(
        "Returns the executive summary, structured key takeaways, and action items. "
        "Returns 404 if the file is still processing."
    ),
)
@limiter.limit("60/minute")
async def get_summary(
    request: Request,
    file_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: SummaryService = Depends(get_summary_service),
) -> SummaryResponse:
    """Fetch the Gemini-generated summary for a completed media file."""
    return await service.get_summary_for_file(file_id, current_user.user_id)
