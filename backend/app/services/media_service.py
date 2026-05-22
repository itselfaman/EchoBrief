"""
MediaService — business logic for media file management.

Handles creation, retrieval, listing, status updates, and deletion
of media file records. Enforces ownership (user_id checks) and
file size/MIME type validation.
"""

from __future__ import annotations

import math
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    AuthorizationError,
    FileSizeExceededError,
    NotFoundError,
    UnsupportedMediaTypeError,
)
from app.models.media_file import FileStatus, MediaFile
from app.models.user import User
from app.schemas.media import MediaFileListResponse, MediaFileResponse, MediaUploadRequest
from app.services.base_service import BaseService
from app.services.storage_service import StorageService


class MediaService(BaseService):
    """
    Encapsulates all business logic related to MediaFile records.

    Responsibilities:
    - Validate upload constraints (size, MIME type)
    - Create and sync user records from JWT identity
    - CRUD operations on MediaFile with ownership enforcement
    - Status transition management
    """

    def __init__(self, db: AsyncSession, storage: StorageService) -> None:
        super().__init__(db)
        self.storage = storage

    # ── Validation ─────────────────────────────────────────────────────────────

    def validate_upload(self, file_size_bytes: int, mime_type: str) -> None:
        """
        Enforce upload constraints before creating a DB record.

        Args:
            file_size_bytes: Size of the uploaded file in bytes.
            mime_type:       MIME type reported by the client.

        Raises:
            FileSizeExceededError:    If file exceeds MAX_FILE_SIZE_BYTES (10 GB).
            UnsupportedMediaTypeError: If MIME type is not in the allowed list.
        """
        if file_size_bytes > settings.MAX_FILE_SIZE_BYTES:
            max_gb = settings.MAX_FILE_SIZE_BYTES / (1024 ** 3)
            raise FileSizeExceededError(
                f"File size {file_size_bytes:,} bytes exceeds the {max_gb:.0f} GB limit.",
                field="file_size_bytes",
            )

        if mime_type not in settings.ALLOWED_MIME_TYPES:
            raise UnsupportedMediaTypeError(
                f"MIME type '{mime_type}' is not supported. "
                f"Allowed types: {', '.join(settings.ALLOWED_MIME_TYPES)}",
                field="mime_type",
            )

    # ── User Sync ──────────────────────────────────────────────────────────────

    async def get_or_create_user(self, user_id: str, email: str) -> User:
        """
        Retrieve an existing user or create a new profile record.

        Called on every authenticated request to ensure the users table
        stays in sync with Supabase auth.users.

        Args:
            user_id: Supabase user UUID string (JWT `sub` claim).
            email:   User's email from JWT `email` claim.

        Returns:
            The User ORM instance.
        """
        uid = uuid.UUID(user_id)
        result = await self.db.execute(select(User).where(User.id == uid))
        user = result.scalar_one_or_none()

        if not user:
            user = User(id=uid, email=email)
            self.db.add(user)
            await self.db.flush()
            self.logger.info("Created new user profile", user_id=user_id, email=email)

        return user

    # ── CRUD ───────────────────────────────────────────────────────────────────

    async def create_media_record(
        self,
        user_id: str,
        payload: MediaUploadRequest,
    ) -> MediaFile:
        """
        Validate and persist a new MediaFile record in 'pending' state.

        Args:
            user_id: Authenticated user's UUID string.
            payload: Validated upload request body.

        Returns:
            Newly created MediaFile ORM instance.
        """
        self.validate_upload(payload.file_size_bytes, payload.mime_type)

        media_file = MediaFile(
            id=uuid.uuid4(),
            user_id=uuid.UUID(user_id),
            file_name=payload.file_name,
            storage_path=payload.storage_path,
            file_size_bytes=payload.file_size_bytes,
            status=FileStatus.PENDING,
        )
        self.db.add(media_file)
        await self.db.flush()

        self.logger.info(
            "Created media file record",
            file_id=str(media_file.id),
            file_name=payload.file_name,
            size_bytes=payload.file_size_bytes,
            user_id=user_id,
        )
        return media_file

    async def get_media_file(self, file_id: uuid.UUID, user_id: str) -> MediaFile:
        """
        Retrieve a single MediaFile, enforcing ownership.

        Args:
            file_id: UUID of the media file.
            user_id: Requesting user's UUID string.

        Returns:
            The MediaFile instance.

        Raises:
            NotFoundError:      If the file doesn't exist.
            AuthorizationError: If the user doesn't own the file.
        """
        result = await self.db.execute(
            select(MediaFile).where(MediaFile.id == file_id)
        )
        media_file = result.scalar_one_or_none()

        if not media_file:
            raise NotFoundError(f"Media file '{file_id}' not found.")

        if str(media_file.user_id) != user_id:
            raise AuthorizationError("You do not have access to this media file.")

        return media_file

    async def list_user_media_files(
        self,
        user_id: str,
        page: int = 1,
        per_page: int = 20,
    ) -> MediaFileListResponse:
        """
        Return a paginated list of the user's media files, newest first.

        Args:
            user_id:  Requesting user's UUID string.
            page:     1-indexed page number.
            per_page: Number of items per page (max 100).

        Returns:
            MediaFileListResponse with items and pagination metadata.
        """
        uid = uuid.UUID(user_id)
        offset = (page - 1) * per_page

        # Total count
        count_result = await self.db.execute(
            select(func.count(MediaFile.id)).where(MediaFile.user_id == uid)
        )
        total = count_result.scalar_one()

        # Paginated results
        result = await self.db.execute(
            select(MediaFile)
            .where(MediaFile.user_id == uid)
            .order_by(MediaFile.created_at.desc())
            .limit(per_page)
            .offset(offset)
        )
        files = list(result.scalars().all())

        return MediaFileListResponse(
            items=[MediaFileResponse.model_validate(f) for f in files],
            total=total,
            page=page,
            per_page=per_page,
            pages=max(1, math.ceil(total / per_page)),
        )

    async def delete_media_file(self, file_id: uuid.UUID, user_id: str) -> None:
        """
        Delete a media file record and its associated storage object.

        Args:
            file_id: UUID of the media file to delete.
            user_id: Requesting user's UUID (for ownership check).

        Raises:
            NotFoundError:      If the file doesn't exist.
            AuthorizationError: If the user doesn't own the file.
        """
        media_file = await self.get_media_file(file_id, user_id)

        # Delete from Supabase Storage (best-effort, don't fail if already gone)
        try:
            self.storage.delete_object(media_file.storage_path)
        except Exception as exc:
            self.logger.warning(
                "Storage delete failed (continuing DB delete)",
                file_id=str(file_id),
                error=str(exc),
            )

        await self.db.delete(media_file)
        await self.db.flush()

        self.logger.info("Deleted media file", file_id=str(file_id), user_id=user_id)

    async def update_status(
        self,
        file_id: uuid.UUID,
        status: FileStatus,
        error_message: str | None = None,
    ) -> MediaFile:
        """
        Transition a MediaFile to a new processing status.

        Args:
            file_id:       UUID of the media file.
            status:        Target FileStatus value.
            error_message: Optional failure reason (set when status='failed').

        Returns:
            Updated MediaFile instance.

        Raises:
            NotFoundError: If the file doesn't exist.
        """
        result = await self.db.execute(
            select(MediaFile).where(MediaFile.id == file_id)
        )
        media_file = result.scalar_one_or_none()

        if not media_file:
            raise NotFoundError(f"Media file '{file_id}' not found for status update.")

        media_file.status = status
        if error_message is not None:
            media_file.error_message = error_message

        await self.db.flush()

        self.logger.info(
            "Updated media file status",
            file_id=str(file_id),
            new_status=status.value,
        )
        return media_file
