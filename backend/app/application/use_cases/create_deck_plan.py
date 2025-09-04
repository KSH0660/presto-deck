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

from app.domain_core.entities.deck import Deck
from app.api.schemas import DeckStatus
from app.domain_core.validators.deck_validators import DeckValidators
from app.data.repositories.deck_repository import DeckRepository
from app.data.repositories.event_repository import EventRepository
from app.infra.messaging.arq_client import ARQClient
from app.infra.messaging.websocket_broadcaster import WebSocketBroadcaster
from app.application.unit_of_work import UnitOfWork
from app.infra.config.logging_config import get_logger, bind_context


class CreateDeckPlanUseCase:
    def __init__(
        self,
        uow: UnitOfWork,
        deck_repo: DeckRepository,
        event_repo: EventRepository,
        arq_client: ARQClient,
        ws_broadcaster: WebSocketBroadcaster,
        llm_client=None,
    ):
        self.uow = uow
        self.deck_repo = deck_repo
        self.event_repo = event_repo
        self.arq_client = arq_client
        self.ws_broadcaster = ws_broadcaster
        self.llm_client = llm_client
        self._log = get_logger("usecase.create_deck_plan")

    async def execute(
        self, user_id: UUID, prompt: str, style_preferences: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Execute the create deck plan use case.

        Returns:
            Dict with deck_id and initial status
        """
        # 1. Domain validation (core business rules)
        bind_context(user_id=str(user_id))
        self._log.info("usecase.start", action="create_deck_plan")
        DeckValidators.validate_prompt(prompt)
        # if style_preferences:
        #     DeckValidators.validate_style_preferences(style_preferences)

        # 2. Create domain entity
        deck_id = uuid4()
        deck = Deck(
            id=deck_id,
            user_id=user_id,
            prompt=prompt,
            status=DeckStatus.PENDING,
            style_preferences=style_preferences or {},
            created_at=datetime.utcnow(),
        )

        # 3. Transaction boundary - all DB operations
        async with self.uow:
            # Save deck
            await self.deck_repo.create(deck)

            # Store initial event
            start_event = {
                "type": "DeckStarted",
                "deck_id": str(deck_id),
                "user_id": str(user_id),
                "prompt": prompt,
                "timestamp": datetime.now(UTC).isoformat(),
                "version": 1,
            }
            await self.event_repo.store_event(deck_id, start_event)

            # Commit transaction
            await self.uow.commit()

        # 4. Side effects after successful commit
        await self._trigger_side_effects(deck_id, user_id, prompt, style_preferences)

        return {
            "deck_id": str(deck_id),
            "status": DeckStatus.PENDING.value,
            "message": "Deck creation initiated",
        }

    async def _trigger_side_effects(
        self,
        deck_id: UUID,
        user_id: UUID,
        prompt: str,
        style_preferences: Dict[str, Any],
    ):
        """Handle side effects after successful database commit."""
        try:
            # 1. Enqueue ARQ background job for LLM planning
            job_id = await self.arq_client.enqueue(
                "generate_deck_plan",
                deck_id=str(deck_id),
                user_id=str(user_id),
                prompt=prompt,
                style_preferences=style_preferences,
            )
            self._log.info(
                "usecase.side_effect.arq_enqueued",
                deck_id=str(deck_id),
                job_id=str(job_id),
            )

            # 2. Broadcast to WebSocket clients
            await self.ws_broadcaster.broadcast_to_user(
                user_id=str(user_id),
                message={
                    "type": "DeckStarted",
                    "deck_id": str(deck_id),
                    "status": DeckStatus.PENDING.value,
                    "job_id": job_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
            self._log.info(
                "usecase.side_effect.ws_broadcast",
                deck_id=str(deck_id),
                status=DeckStatus.PENDING.value,
            )

        except Exception as e:
            # Log error but don't fail the use case
            # The deck is already created, background processes will retry
            self._log.exception(
                "usecase.side_effect.error", deck_id=str(deck_id), error=str(e)
            )
            # In production: logger.error("Side effect failed", extra={"deck_id": deck_id, "error": str(e)})
