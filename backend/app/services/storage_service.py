"""
StorageService — Supabase Storage operations.

Handles file URL generation for workers to download media assets.
Uses the Supabase service role key for elevated bucket access.
"""

from __future__ import annotations

from supabase import Client, create_client

from app.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)


class StorageService:
    """
    Manages all interactions with Supabase Storage.

    This is a standalone service (not inheriting BaseService) because it
    doesn't require a database session — it operates purely against the
    Supabase Storage API using the admin client.

    Responsibilities:
    - Generate signed download URLs for media assets (for workers)
    - Delete storage objects when a media file is deleted
    - Validate storage paths
    """

    def __init__(self) -> None:
        """Initialise the Supabase admin client with the service role key."""
        try:
            self._client: Client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_ROLE_KEY,
            )
            self._bucket = settings.SUPABASE_STORAGE_BUCKET
        except Exception as exc:
            logger.error("Failed to initialise Supabase client", error=str(exc))
            raise ServiceUnavailableError(
                "Storage service is currently unavailable."
            ) from exc

    def get_signed_download_url(
        self,
        storage_path: str,
        expires_in: int = 3600,
    ) -> str:
        """
        Generate a time-limited signed URL for downloading a media asset.

        Args:
            storage_path: Path within the bucket (e.g. "user_id/file_id/name.mp3").
            expires_in:   URL validity in seconds (default: 1 hour).

        Returns:
            A fully-qualified signed URL string.

        Raises:
            ServiceUnavailableError: If Supabase Storage returns an error.
        """
        try:
            response = self._client.storage.from_(self._bucket).create_signed_url(
                path=storage_path,
                expires_in=expires_in,
            )
            signed_url: str = response["signedURL"]
            logger.info(
                "Generated signed download URL",
                storage_path=storage_path,
                expires_in=expires_in,
            )
            return signed_url
        except Exception as exc:
            logger.error(
                "Failed to generate signed URL",
                storage_path=storage_path,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                f"Could not generate download URL for: {storage_path}"
            ) from exc

    def delete_object(self, storage_path: str) -> None:
        """
        Permanently remove a file from Supabase Storage.

        Args:
            storage_path: Bucket-relative path to the object.

        Raises:
            ServiceUnavailableError: If the delete operation fails.
        """
        try:
            self._client.storage.from_(self._bucket).remove([storage_path])
            logger.info("Deleted storage object", storage_path=storage_path)
        except Exception as exc:
            logger.error(
                "Failed to delete storage object",
                storage_path=storage_path,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                f"Could not delete storage object: {storage_path}"
            ) from exc

    def get_public_url(self, storage_path: str) -> str:
        """
        Return the public URL for an object in a public bucket.

        Args:
            storage_path: Bucket-relative path to the object.

        Returns:
            Public URL string.
        """
        return self._client.storage.from_(self._bucket).get_public_url(storage_path)


# Module-level singleton (initialised lazily)
_storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    """Return the shared StorageService singleton."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
