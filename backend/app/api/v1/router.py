"""V1 API router — aggregates all v1 route modules."""

from fastapi import APIRouter

from app.api.v1.media import router as media_router
from app.api.v1.summaries import router as summaries_router
from app.api.v1.transcripts import router as transcripts_router

v1_router = APIRouter(prefix="/v1")

v1_router.include_router(media_router)
v1_router.include_router(transcripts_router)
v1_router.include_router(summaries_router)
