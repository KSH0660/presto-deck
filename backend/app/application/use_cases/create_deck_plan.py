"""
Use Case: Create Deck Plan

This use case handles:
1. Validating deck creation request
2. Creating deck entity in PENDING status
3. Enqueueing LLM job for deck planning
4. Publishing DeckStarted event
"""

from typing import Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, UTC

from app.domain.entities.deck import Deck
from app.domain.value_objects.deck_status import DeckStatus
from app.domain.validators.deck_validators import DeckValidators
from app.application.unit_of_work import UnitOfWork
from app.application.ports import MessageBrokerPort, WebSocketBroadcasterPort
from app.application.services.template_selector import TemplateSelectionService
from app.infra.config.logging_config import get_logger, bind_context


class CreateDeckPlanUseCase:
    """
    Use case for creating a new deck and initiating the planning process.

    This use case handles the complete workflow of:
    1. Validating the deck creation request
    2. Selecting appropriate template type
    3. Creating the deck entity
    4. Storing initial events
    5. Initiating the background generation pipeline
    """

    def __init__(
        self,
        uow: UnitOfWork,
        message_broker: MessageBrokerPort,
        ws_broadcaster: WebSocketBroadcasterPort,
        template_selector: TemplateSelectionService,
    ):
        self.uow = uow
        self.message_broker = message_broker
        self.ws_broadcaster = ws_broadcaster
        self.template_selector = template_selector
        self._log = get_logger("usecase.create_deck_plan")

    async def execute(
        self, user_id: UUID, prompt: str, style_preferences: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Execute the create deck plan use case.

        Args:
            user_id: ID of the user creating the deck
            prompt: User's prompt for deck generation
            style_preferences: Optional style preferences

        Returns:
            Dict with deck_id and initial status
        """
        # 1. Domain validation (core business rules)
        bind_context(user_id=str(user_id))
        self._log.info("usecase.start", action="create_deck_plan")
        DeckValidators.validate_prompt(prompt)

        # 2. Select appropriate template type using application service
        template_type = await self.template_selector.select_deck_template_type(
            prompt=prompt, style_preferences=style_preferences or {}
        )

        # 3. Get enhanced style preferences
        enhanced_style_preferences = (
            await self.template_selector.get_template_style_preferences(
                template_type=template_type, custom_preferences=style_preferences
            )
        )

        # 4. Create domain entity
        deck_id = uuid4()
        deck = Deck(
            id=deck_id,
            user_id=user_id,
            prompt=prompt,
            status=DeckStatus.PENDING,
            style_preferences=enhanced_style_preferences,
            created_at=datetime.utcnow(),
            template_type=template_type,
        )

        # 5. Transaction boundary - all DB operations
        async with self.uow:
            # Save deck
            await self.uow.deck_repo.create(deck)

            # Store initial event
            start_event = {
                "type": "DeckStarted",
                "deck_id": str(deck_id),
                "user_id": str(user_id),
                "prompt": prompt,
                "template_type": template_type.value,
                "timestamp": datetime.now(UTC).isoformat(),
                "version": 1,
            }
            await self.uow.event_repo.store_event(deck_id, start_event)

            # Commit transaction
            await self.uow.commit()

        # 6. Side effects after successful commit
        await self._trigger_side_effects(deck, user_id)

        return {
            "deck_id": str(deck_id),
            "status": DeckStatus.PENDING.value,
            "template_type": template_type.value,
            "message": "Deck creation initiated",
        }

    async def _trigger_side_effects(self, deck: Deck, user_id: UUID):
        """Handle side effects after successful database commit."""
        try:
            # 1. Enqueue background job for deck generation pipeline
            job_id = await self.message_broker.enqueue_job(
                "generate_deck_plan",
                deck_id=str(deck.id),
                user_id=str(user_id),
                prompt=deck.prompt,
                template_type=deck.template_type.value if deck.template_type else None,
                style_preferences=deck.style_preferences,
            )
            self._log.info(
                "usecase.side_effect.job_enqueued",
                deck_id=str(deck.id),
                job_id=str(job_id),
            )

            # 2. Broadcast to WebSocket clients
            await self.ws_broadcaster.broadcast_to_user(
                user_id=str(user_id),
                message={
                    "type": "DeckStarted",
                    "deck_id": str(deck.id),
                    "status": deck.status.value,
                    "template_type": (
                        deck.template_type.value if deck.template_type else None
                    ),
                    "job_id": job_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
            self._log.info(
                "usecase.side_effect.ws_broadcast",
                deck_id=str(deck.id),
                status=deck.status.value,
            )

        except Exception as e:
            # Log error but don't fail the use case
            # The deck is already created, background processes will retry
            self._log.exception(
                "usecase.side_effect.error", deck_id=str(deck.id), error=str(e)
            )
