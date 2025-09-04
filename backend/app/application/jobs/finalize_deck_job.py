"""
Background Job: Finalize Deck

This job handles finalizing a deck when all slides are complete.
It marks the deck as COMPLETED and performs cleanup tasks.
"""

from typing import List
from uuid import UUID
from datetime import datetime, timezone

from app.api.schemas import DeckStatus
from app.data.repositories.deck_repository import DeckRepository
from app.data.repositories.slide_repository import SlideRepository
from app.data.repositories.event_repository import EventRepository
from app.infra.messaging.websocket_broadcaster import WebSocketBroadcaster
from app.application.unit_of_work import UnitOfWork
from app.infra.config.logging_config import get_logger, bind_context


class FinalizeDeckJob:
    """
    Background job for finalizing a deck when all slides are complete.

    This job:
    1. Validates all slides are complete
    2. Updates deck status to COMPLETED
    3. Sets completion timestamp
    4. Publishes final events
    """

    def __init__(
        self,
        uow: UnitOfWork,
        deck_repo: DeckRepository,
        slide_repo: SlideRepository,
        event_repo: EventRepository,
        ws_broadcaster: WebSocketBroadcaster,
    ):
        self.uow = uow
        self.deck_repo = deck_repo
        self.slide_repo = slide_repo
        self.event_repo = event_repo
        self.ws_broadcaster = ws_broadcaster
        self._log = get_logger("job.finalize_deck")

    async def execute(self, deck_id: UUID) -> bool:
        """
        Execute deck finalization job.

        Returns:
            bool: True if deck was successfully finalized
        """
        bind_context(deck_id=str(deck_id))
        self._log.info("job.start")

        try:
            # 1. Get deck and validate state
            deck = await self.deck_repo.get_by_id(deck_id)
            if not deck:
                raise ValueError(f"Deck {deck_id} not found")

            if deck.status == DeckStatus.COMPLETED:
                self._log.info("job.already_completed")
                return True

            # 2. Get all slides for the deck
            slides = await self.slide_repo.get_by_deck_id(deck_id)

            # 3. Validate all slides are complete
            incomplete_slides = [s for s in slides if not s.is_complete()]
            if incomplete_slides:
                self._log.warning(
                    "job.incomplete_slides",
                    incomplete_count=len(incomplete_slides),
                    total_slides=len(slides),
                )
                return False

            # 4. Update deck to COMPLETED status
            async with self.uow:
                deck.status = DeckStatus.COMPLETED
                deck.completed_at = datetime.now(timezone.utc)
                await self.deck_repo.update(deck)

                # 5. Store completion event
                completion_event = {
                    "type": "DeckCompleted",
                    "deck_id": str(deck_id),
                    "slide_count": len(slides),
                    "completed_at": deck.completed_at.isoformat(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "version": 1,
                }
                await self.event_repo.store_event(deck_id, completion_event)
                await self.uow.commit()

            # 6. Broadcast completion to all subscribers
            await self.ws_broadcaster.broadcast_to_deck(deck_id, completion_event)

            # 7. Cleanup tasks
            await self._perform_cleanup_tasks(deck_id, slides)

            self._log.info(
                "job.completed",
                slide_count=len(slides),
                completion_time=deck.completed_at.isoformat(),
            )
            return True

        except Exception as e:
            self._log.error("job.failed", error=str(e), exc_info=True)

            # Mark deck as failed if finalization fails
            try:
                await self._mark_deck_failed(deck_id, str(e))
            except Exception as cleanup_error:
                self._log.error("job.cleanup_failed", error=str(cleanup_error))

            return False

    async def _perform_cleanup_tasks(self, deck_id: UUID, slides: List):
        """Perform cleanup and optimization tasks after deck completion."""
        self._log.info("job.cleanup.start", slide_count=len(slides))

        try:
            # TODO: Implement cleanup tasks such as:
            # - Optimize images in slides
            # - Generate PDF version
            # - Update search indexes
            # - Clear temporary caches

            self._log.info("job.cleanup.completed")

        except Exception as e:
            self._log.warning("job.cleanup.failed", error=str(e))
            # Cleanup failures shouldn't fail the main job

    async def _mark_deck_failed(self, deck_id: UUID, error_message: str):
        """Mark deck as failed if finalization fails."""
        try:
            deck = await self.deck_repo.get_by_id(deck_id)
            if deck:
                deck.status = DeckStatus.FAILED
                await self.deck_repo.update(deck)

                # Publish failure event
                failure_event = {
                    "type": "DeckFinalizationFailed",
                    "deck_id": str(deck_id),
                    "error": error_message,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "version": 1,
                }
                await self.event_repo.store_event(deck_id, failure_event)
                await self.ws_broadcaster.broadcast_to_deck(deck_id, failure_event)

        except Exception as e:
            self._log.error("job.mark_failed.error", error=str(e))
