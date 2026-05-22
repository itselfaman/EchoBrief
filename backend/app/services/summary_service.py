"""
SummaryService — business logic for summary retrieval and persistence.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.models.media_file import MediaFile
from app.models.summary import Summary
from app.schemas.summary import SummaryResponse
from app.services.base_service import BaseService


class SummaryService(BaseService):
    """
    Encapsulates business logic for Summary records.

    Like TranscriptService, all read operations enforce ownership
    by verifying the requesting user owns the parent media file.
    """

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_summary_for_file(
        self,
        file_id: uuid.UUID,
        user_id: str,
    ) -> SummaryResponse:
        """
        Retrieve the AI-generated summary for a specific media file.

        Args:
            file_id: UUID of the parent media file.
            user_id: Requesting user's UUID string (ownership check).

        Returns:
            SummaryResponse schema.

        Raises:
            NotFoundError:      If no summary exists or media file not found.
            AuthorizationError: If the user doesn't own the media file.
        """
        # Ownership check via media file lookup
        file_result = await self.db.execute(
            select(MediaFile).where(MediaFile.id == file_id)
        )
        media_file = file_result.scalar_one_or_none()

        if not media_file:
            raise NotFoundError(f"Media file '{file_id}' not found.")

        if str(media_file.user_id) != user_id:
            raise AuthorizationError("You do not have access to this resource.")

        # Fetch the summary
        summary_result = await self.db.execute(
            select(Summary).where(Summary.file_id == file_id)
        )
        summary = summary_result.scalar_one_or_none()

        if not summary:
            raise NotFoundError(
                f"Summary not yet available for file '{file_id}'. "
                "Processing may still be in progress."
            )

        self.logger.info("Fetched summary", file_id=str(file_id), user_id=user_id)
        return SummaryResponse.model_validate(summary)

    async def save_summary(
        self,
        file_id: uuid.UUID,
        executive_summary: str,
        key_takeaways: list[dict],
        action_items: list[dict],
    ) -> Summary:
        """
        Persist a new Summary record (called by Dramatiq workers only).

        Args:
            file_id:           Parent media file UUID.
            executive_summary: 3-5 paragraph narrative summary.
            key_takeaways:     List of structured insight dicts.
            action_items:      List of structured action item dicts.

        Returns:
            Newly created Summary instance.
        """
        summary = Summary(
            file_id=file_id,
            executive_summary=executive_summary,
            key_takeaways=key_takeaways,
            action_items=action_items,
        )
        self.db.add(summary)
        await self.db.flush()

        self.logger.info(
            "Saved summary",
            file_id=str(file_id),
            takeaway_count=len(key_takeaways),
            action_count=len(action_items),
        )
        return summary
