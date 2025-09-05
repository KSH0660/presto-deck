"""
Command: Create Deck Plan

This command handles:
1. Validating deck creation request
2. Creating deck entity in PENDING status
3. Enqueueing background job for deck planning
4. Publishing DeckStarted event
"""

from typing import Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

from app.domain.entities.deck import Deck
from app.api.schemas import DeckStatus
from app.domain.validators.deck_validators import DeckValidators
from app.data.repositories.deck_repository import DeckRepository
from app.data.repositories.event_repository import EventRepository
from app.infra.messaging.arq_client import ARQClient
from app.infra.messaging.websocket_broadcaster import WebSocketBroadcaster
from app.application.unit_of_work import UnitOfWork
from app.infra.config.logging_config import get_logger, bind_context


class CreateDeckPlanCommand:
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
        self._log = get_logger("command.create_deck_plan")

    async def execute(
        self, user_id: UUID, prompt: str, style_preferences: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Execute the create deck plan command.

        Returns:
            Dict containing deck_id, status, and message
        """
        bind_context(user_id=str(user_id))
        deck_id = uuid4()
        bind_context(deck_id=str(deck_id))

        self._log.info(
            "command.start",
            prompt_length=len(prompt),
            has_style_preferences=bool(style_preferences),
        )

        # 1. Validate input using domain rules
        DeckValidators.validate_prompt(prompt)
        if style_preferences:
            DeckValidators.validate_style_preferences(style_preferences)

        # 2. Create deck entity in PENDING status
        deck = Deck(
            id=deck_id,
            user_id=user_id,
            prompt=prompt,
            status=DeckStatus.PENDING,
            style_preferences=style_preferences or {},
            template_type=None,  # Will be determined later
            slide_count=0,
            created_at=datetime.utcnow(),
            completed_at=None,
        )

        # 3. Database transaction
        async with self.uow:
            # Save deck
            await self.deck_repo.create(deck)

            # Store initial event
            deck_started_event = {
                "type": "DeckStarted",
                "deck_id": str(deck_id),
                "user_id": str(user_id),
                "prompt": prompt,
                "timestamp": datetime.utcnow().isoformat(),
                "version": 1,
            }
            await self.event_repo.store_event(deck_id, deck_started_event)
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
                "command.side_effect.arq_enqueued",
                deck_id=str(deck_id),
                job_id=str(job_id),
            )

            # 2. Broadcast WebSocket event for real-time updates
            deck_started_event = {
                "type": "DeckStarted",
                "deck_id": str(deck_id),
                "status": DeckStatus.PENDING.value,
                "timestamp": datetime.utcnow().isoformat(),
                "version": 1,
            }
            await self.ws_broadcaster.broadcast_to_user(user_id, deck_started_event)
            self._log.info(
                "command.side_effect.websocket_broadcasted", deck_id=str(deck_id)
            )

        except Exception as e:
            # Log side effect failures but don't fail the main operation
            self._log.error(
                "command.side_effect.failed",
                deck_id=str(deck_id),
                error=str(e),
                exc_info=True,
            )
