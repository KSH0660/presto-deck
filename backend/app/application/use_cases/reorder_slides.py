"""
Use Case: Reorder Slides

This use case handles reordering slides within a deck:
1. Validating the new slide order
2. Updating slide order values
3. Publishing reorder events
4. Notifying users via WebSocket
"""

from typing import Dict, Any, List
from uuid import UUID
from datetime import datetime, UTC

from app.domain.entities.slide import Slide
from app.domain.services.deck_orchestration import DeckOrchestrationService
from app.application.unit_of_work import UnitOfWork
from app.application.ports import WebSocketBroadcasterPort
from app.infra.config.logging_config import get_logger, bind_context


class ReorderSlidesUseCase:
    """
    Use case for reordering slides within a deck.

    This use case handles the business logic for changing the order
    of slides while maintaining data consistency and user notifications.
    """

    def __init__(self, uow: UnitOfWork, ws_broadcaster: WebSocketBroadcasterPort):
        self.uow = uow
        self.ws_broadcaster = ws_broadcaster
        self.orchestration_service = DeckOrchestrationService()
        self._log = get_logger("usecase.reorder_slides")

    async def execute(
        self, deck_id: UUID, user_id: UUID, new_slide_order: List[UUID]
    ) -> Dict[str, Any]:
        """
        Execute the reorder slides use case.

        Args:
            deck_id: ID of the deck containing the slides
            user_id: ID of the user reordering the slides
            new_slide_order: List of slide IDs in the desired new order

        Returns:
            Dict with reorder status and updated slide information
        """
        bind_context(deck_id=str(deck_id), user_id=str(user_id))
        self._log.info(
            "usecase.start", action="reorder_slides", slide_count=len(new_slide_order)
        )

        # 1. Load and validate within transaction
        async with self.uow:
            # Get deck to verify ownership
            deck = await self.uow.deck_repo.get_by_id(deck_id)
            if not deck:
                raise ValueError(f"Deck {deck_id} not found")

            if deck.user_id != user_id:
                raise ValueError(f"Deck {deck_id} does not belong to user {user_id}")

            # Get all current slides for the deck
            current_slides = await self.uow.slide_repo.get_by_deck_id(deck_id)

            if not current_slides:
                raise ValueError(f"No slides found for deck {deck_id}")

            # 2. Validate the new order using domain service
            try:
                reordered_slides = self.orchestration_service.reorder_slides(
                    slides=current_slides, new_order=new_slide_order
                )
            except ValueError as e:
                self._log.warning("usecase.validation_failed", error=str(e))
                return {
                    "deck_id": str(deck_id),
                    "success": False,
                    "message": f"Invalid slide order: {str(e)}",
                }

            # 3. Update slides in repository
            updated_slides = []
            for slide in reordered_slides:
                updated_slide = await self.uow.slide_repo.update(slide)
                updated_slides.append(updated_slide)

            # 4. Store reorder event
            reorder_event = {
                "type": "SlideReordered",
                "deck_id": str(deck_id),
                "user_id": str(user_id),
                "old_order": [
                    str(s.id) for s in sorted(current_slides, key=lambda x: x.order)
                ],
                "new_order": [
                    str(s.id) for s in sorted(reordered_slides, key=lambda x: x.order)
                ],
                "timestamp": datetime.now(UTC).isoformat(),
                "version": await self._get_next_version(deck_id),
            }
            await self.uow.event_repo.store_event(deck_id, reorder_event)

            # Update deck timestamp
            deck.updated_at = datetime.utcnow()
            await self.uow.deck_repo.update(deck)

            # Commit transaction
            await self.uow.commit()

        # 5. Side effects after successful commit
        await self._trigger_reorder_notifications(deck_id, user_id, updated_slides)

        self._log.info("usecase.success", updated_count=len(updated_slides))

        # Prepare slide summary for response
        slide_summaries = [
            {"slide_id": str(slide.id), "order": slide.order, "title": slide.title}
            for slide in sorted(updated_slides, key=lambda x: x.order)
        ]

        return {
            "deck_id": str(deck_id),
            "success": True,
            "slides": slide_summaries,
            "message": f"Successfully reordered {len(updated_slides)} slides",
        }

    async def _get_next_version(self, deck_id: UUID) -> int:
        """Get the next version number for events."""
        try:
            existing_events = await self.uow.event_repo.get_events_by_deck_id(deck_id)
            return len(existing_events) + 1
        except Exception:
            return 1

    async def _trigger_reorder_notifications(
        self, deck_id: UUID, user_id: UUID, updated_slides: List[Slide]
    ):
        """Handle notifications after successful slide reordering."""
        try:
            slide_order_info = [
                {"slide_id": str(slide.id), "order": slide.order, "title": slide.title}
                for slide in sorted(updated_slides, key=lambda x: x.order)
            ]

            # Broadcast to user
            await self.ws_broadcaster.broadcast_to_user(
                user_id=str(user_id),
                message={
                    "type": "SlideReordered",
                    "deck_id": str(deck_id),
                    "slides": slide_order_info,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

            # Broadcast to deck channel for real-time collaboration
            await self.ws_broadcaster.broadcast_to_deck(
                deck_id=str(deck_id),
                message={
                    "type": "SlideReordered",
                    "deck_id": str(deck_id),
                    "slides": slide_order_info,
                    "updated_by": str(user_id),
                    "message": "Slide order has been updated",
                },
            )

            self._log.info("usecase.notifications_sent")

        except Exception as e:
            # Log error but don't fail the use case
            self._log.exception("usecase.notification_error", error=str(e))
