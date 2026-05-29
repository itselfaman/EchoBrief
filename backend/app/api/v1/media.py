"""
Media API endpoints — file upload registration, listing, status, and deletion.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, status, HTTPException

from app.api.deps import get_current_user, get_media_service
from app.config import settings
from app.core.rate_limit import limiter
from app.core.security import CurrentUser
from app.schemas.common import MessageResponse
from app.schemas.media import (
    MediaFileListResponse,
    MediaFileResponse,
    MediaUploadRequest,
    MediaUploadResponse,
)
from app.services.media_service import MediaService
from app.workers.tasks import process_media_task

router = APIRouter(prefix="/media", tags=["Media"])


@router.post(
    "/upload",
    response_model=MediaUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Register uploaded file and enqueue processing",
    description=(
        "After the client uploads a file directly to Supabase Storage, "
        "call this endpoint with the file metadata. The backend creates a "
        "DB record and enqueues the Dramatiq worker. Returns 202 immediately."
    ),
)
@limiter.limit(lambda: f"{settings.RATE_LIMIT_UPLOADS_PER_MINUTE}/minute")
async def upload_media(
    request: Request,
    payload: MediaUploadRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: MediaService = Depends(get_media_service),
) -> MediaUploadResponse:
    """Register file metadata and enqueue the processing pipeline."""
    # Sync user profile (upsert)
    await service.get_or_create_user(current_user.user_id, current_user.email)

    # Create the DB record (validates size + MIME type)
    media_file = await service.create_media_record(current_user.user_id, payload)

    # Enqueue the Dramatiq background task
    process_media_task.send(str(media_file.id))

    return MediaUploadResponse(
        message="File successfully queued for processing.",
        file_id=media_file.id,
    )


@router.get(
    "/",
    response_model=MediaFileListResponse,
    summary="List all media files for the current user",
)
@limiter.limit("60/minute")
async def list_media_files(
    request: Request,
    page: int = 1,
    per_page: int = 20,
    current_user: CurrentUser = Depends(get_current_user),
    service: MediaService = Depends(get_media_service),
) -> MediaFileListResponse:
    """Return a paginated list of the user's media files, newest first."""
    return await service.list_user_media_files(
        user_id=current_user.user_id,
        page=max(1, page),
        per_page=min(100, max(1, per_page)),
    )


@router.get(
    "/{file_id}",
    response_model=MediaFileResponse,
    summary="Get status and details for a single media file",
)
@limiter.limit("60/minute")
async def get_media_file(
    request: Request,
    file_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: MediaService = Depends(get_media_service),
) -> MediaFileResponse:
    """Retrieve metadata and current processing status for a media file."""
    media_file = await service.get_media_file(file_id, current_user.user_id)
    return MediaFileResponse.model_validate(media_file)


@router.delete(
    "/{file_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a media file and all associated data",
)
@limiter.limit("20/minute")
async def delete_media_file(
    request: Request,
    file_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: MediaService = Depends(get_media_service),
) -> MessageResponse:
    """
    Permanently delete a media file, its storage object, transcript, and summary.
    Cascade deletes are handled at the database level.
    """
    await service.delete_media_file(file_id, current_user.user_id)
    return MessageResponse(message="Media file deleted successfully.")

@router.post(
    "/{file_id}/retry",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry a failed media file processing job",
)
@limiter.limit("10/minute")
async def retry_media_file(
    request: Request,
    file_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: MediaService = Depends(get_media_service),
) -> MessageResponse:
    """Retry a failed media file by resetting its status to pending and re-enqueueing."""
    from app.models.media_file import FileStatus
    media_file = await service.get_media_file(file_id, current_user.user_id)
    
    if media_file.status != FileStatus.FAILED:
        raise HTTPException(status_code=400, detail="Only failed files can be retried.")
        
    media_file.status = FileStatus.PENDING
    media_file.error_message = None
    media_file.processing_message = "Re-queued for processing..."
    await service.db.commit()
    
    process_media_task.send(str(file_id))
    return MessageResponse(message="File successfully re-queued for processing.")
