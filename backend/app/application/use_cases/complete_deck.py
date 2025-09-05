"""
Use Case: Complete Deck

This use case handles the completion of deck generation:
1. Validating deck completion requirements
2. Updating deck status to COMPLETED
3. Publishing completion events
4. Notifying users via WebSocket
"""

from typing import Dict, Any, List
from uuid import UUID
from datetime import datetime, UTC

from app.domain.entities.deck import Deck
from app.domain.entities.slide import Slide
from app.domain.value_objects.deck_status import DeckStatus
from app.domain.services.deck_orchestration import DeckOrchestrationService
from app.application.unit_of_work import UnitOfWork
from app.application.ports import WebSocketBroadcasterPort
from app.infra.config.logging_config import get_logger, bind_context


class CompleteDeckUseCase:
    """
    Use case for completing deck generation and finalizing the deck.

    This use case coordinates the final steps of deck generation,
    including validation, status updates, and user notifications.
    """

    def __init__(self, uow: UnitOfWork, ws_broadcaster: WebSocketBroadcasterPort):
        self.uow = uow
        self.ws_broadcaster = ws_broadcaster
        self.orchestration_service = DeckOrchestrationService()
        self._log = get_logger("usecase.complete_deck")

    async def execute(self, deck_id: UUID, user_id: UUID) -> Dict[str, Any]:
        """
        Execute the complete deck use case.

        Args:
            deck_id: ID of the deck to complete
            user_id: ID of the user who owns the deck

        Returns:
            Dict with completion status and details
        """
        bind_context(deck_id=str(deck_id), user_id=str(user_id))
        self._log.info("usecase.start", action="complete_deck")

        # 1. Load deck and slides within transaction
        async with self.uow:
            # Get current deck state
            deck = await self.uow.deck_repo.get_by_id(deck_id)
            if not deck:
                raise ValueError(f"Deck {deck_id} not found")

            if deck.user_id != user_id:
                raise ValueError(f"Deck {deck_id} does not belong to user {user_id}")

            # Get all slides for the deck
            slides = await self.uow.slide_repo.get_by_deck_id(deck_id)

            # 2. Validate completion requirements using domain service
            can_complete, reason = self.orchestration_service.can_mark_deck_complete(
                deck, slides
            )

            if not can_complete:
                self._log.warning("usecase.validation_failed", reason=reason)
                return {
                    "deck_id": str(deck_id),
                    "status": deck.status.value,
                    "success": False,
                    "message": f"Cannot complete deck: {reason}",
                }

            # 3. Mark deck as completed using domain method
            deck.mark_as_completed()

            # Update deck in repository
            await self.uow.deck_repo.update(deck)

            # 4. Store completion event
            completion_event = {
                "type": "DeckCompleted",
                "deck_id": str(deck_id),
                "user_id": str(user_id),
                "slide_count": len(slides),
                "completed_at": deck.completed_at.isoformat(),
                "timestamp": datetime.now(UTC).isoformat(),
                "version": await self._get_next_version(deck_id),
            }
            await self.uow.event_repo.store_event(deck_id, completion_event)

            # Commit transaction
            await self.uow.commit()

        # 5. Side effects after successful commit
        await self._trigger_completion_notifications(deck, slides, user_id)

        self._log.info("usecase.success", slide_count=len(slides))

        return {
            "deck_id": str(deck_id),
            "status": DeckStatus.COMPLETED.value,
            "slide_count": len(slides),
            "completed_at": deck.completed_at.isoformat(),
            "success": True,
            "message": "Deck completed successfully",
        }

    async def _get_next_version(self, deck_id: UUID) -> int:
        """Get the next version number for events."""
        try:
            existing_events = await self.uow.event_repo.get_events_by_deck_id(deck_id)
            return len(existing_events) + 1
        except Exception:
            return 1

    async def _trigger_completion_notifications(
        self, deck: Deck, slides: List[Slide], user_id: UUID
    ):
        """Handle notifications after successful deck completion."""
        try:
            # Broadcast completion to WebSocket clients
            await self.ws_broadcaster.broadcast_to_user(
                user_id=str(user_id),
                message={
                    "type": "DeckCompleted",
                    "deck_id": str(deck.id),
                    "status": deck.status.value,
                    "slide_count": len(slides),
                    "completed_at": deck.completed_at.isoformat(),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

            # Also broadcast to any deck-specific channels
            await self.ws_broadcaster.broadcast_to_deck(
                deck_id=str(deck.id),
                message={
                    "type": "DeckCompleted",
                    "deck_id": str(deck.id),
                    "slide_count": len(slides),
                    "completed_at": deck.completed_at.isoformat(),
                    "message": "Deck generation completed",
                },
            )

            self._log.info("usecase.notifications_sent")

        except Exception as e:
            # Log error but don't fail the use case
            self._log.exception("usecase.notification_error", error=str(e))
