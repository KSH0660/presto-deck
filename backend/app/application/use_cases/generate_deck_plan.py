"""
Use Case: Generate Deck Plan (Background Worker Task)

This use case handles the actual LLM-based deck planning that runs as a background job.
It uses structured output to generate a comprehensive deck plan with slides.
"""

from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, UTC, timezone

from app.domain.entities.slide import Slide
from app.api.schemas import DeckStatus
from app.data.repositories.deck_repository import DeckRepository
from app.data.repositories.slide_repository import SlideRepository
from app.data.repositories.event_repository import EventRepository
from app.infra.messaging.websocket_broadcaster import WebSocketBroadcaster
from app.infra.llm.langchain_client import LangChainClient
from app.application.prompts.deck_planning import DeckPlan, DeckPlanningPrompts
from app.application.unit_of_work import UnitOfWork
from app.infra.config.logging_config import get_logger, bind_context


class GenerateDeckPlanUseCase:
    """
    Background use case for generating deck plans using LLM with structured output.

    This runs as an ARQ worker task and handles the actual LLM interaction
    for deck planning and slide generation.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        deck_repo: DeckRepository,
        slide_repo: SlideRepository,
        event_repo: EventRepository,
        ws_broadcaster: WebSocketBroadcaster,
        llm_client: LangChainClient,
    ):
        self.uow = uow
        self.deck_repo = deck_repo
        self.slide_repo = slide_repo
        self.event_repo = event_repo
        self.ws_broadcaster = ws_broadcaster
        self.llm_client = llm_client
        self._log = get_logger("usecase.generate_deck_plan")

    async def execute(
        self,
        deck_id: UUID,
        user_id: UUID,
        prompt: str,
        style_preferences: Optional[Dict[str, Any]] = None,
        slide_count: Optional[int] = None,
        sources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute deck plan generation using structured LLM output.

        Args:
            deck_id: The deck to generate plan for
            user_id: The user who owns the deck
            prompt: The user's content prompt
            style_preferences: Optional style preferences
            slide_count: Hint for number of slides
            sources: Optional reference materials

        Returns:
            Dict with generation results and slide count
        """

        bind_context(deck_id=str(deck_id), user_id=str(user_id))
        self._log.info("usecase.start", action="generate_deck_plan")
        # 1. Validate deck exists and is in correct state
        deck = await self.deck_repo.get_by_id(deck_id)
        if not deck:
            raise ValueError(f"Deck {deck_id} not found")

        if deck.user_id != user_id:
            raise ValueError(f"Deck {deck_id} does not belong to user {user_id}")

        if deck.status != DeckStatus.PENDING:
            raise ValueError(f"Deck {deck_id} is not in PENDING status")

        try:
            # 2. Update deck status to PLANNING
            await self._update_deck_status(
                deck_id, DeckStatus.PLANNING, "Starting LLM planning"
            )

            # 3. Generate structured deck plan using LLM
            deck_plan = await self._generate_structured_deck_plan(
                prompt, style_preferences, slide_count, sources
            )

            # 4. Create slide entities from plan
            slides = await self._create_slides_from_plan(deck_id, deck_plan)

            # 5. Update deck status to GENERATING
            await self._update_deck_status(
                deck_id, DeckStatus.GENERATING, "Plan complete, generating slides"
            )

            # 6. Trigger slide content generation jobs
            await self._enqueue_slide_generation_jobs(deck_id, slides)

            return {
                "deck_id": str(deck_id),
                "status": "plan_generated",
                "slide_count": len(slides),
                "deck_title": deck_plan.title,
                "estimated_duration": deck_plan.estimated_duration,
            }

        except Exception as e:
            # Mark deck as failed and propagate error
            await self._update_deck_status(
                deck_id, DeckStatus.FAILED, f"Planning failed: {str(e)}"
            )
            self._log.exception("usecase.error", error=str(e))
            raise

    async def _generate_structured_deck_plan(
        self,
        prompt: str,
        style_preferences: Optional[Dict[str, Any]] = None,
        slide_count: Optional[int] = None,
        sources: Optional[List[str]] = None,
    ) -> DeckPlan:
        """Generate structured deck plan using LLM with Pydantic models."""

        # Use domain-specific prompts
        system_prompt = DeckPlanningPrompts.get_system_prompt()
        user_prompt = DeckPlanningPrompts.get_user_prompt(
            user_prompt=prompt,
            style_preferences=style_preferences,
            slide_count=slide_count,
            sources=sources,
        )

        # Generate structured output with retry logic
        messages = self.llm_client.create_messages(user_prompt, system_prompt)
        deck_plan = await self.llm_client.invoke_with_retry(
            messages=messages, response_model=DeckPlan, max_retries=3
        )

        return deck_plan

    async def _create_slides_from_plan(
        self, deck_id: UUID, deck_plan: DeckPlan
    ) -> List[Slide]:
        """Create slide entities from the generated plan."""

        slides = []

        async with self.uow:
            for slide_outline in deck_plan.slides:
                # Create slide entity
                slide = Slide(
                    id=None,  # Will be set by repository
                    deck_id=deck_id,
                    order=slide_outline.order,
                    title=slide_outline.title,
                    content_outline=slide_outline.content,
                    html_content=None,  # Will be generated later
                    presenter_notes=slide_outline.notes,
                    template_filename="content_slide.html",  # Will be updated by template selection
                    created_at=datetime.now(timezone.utc),
                )

                # Save to repository
                created_slide = await self.slide_repo.create(slide)
                slides.append(created_slide)

                # Store slide created event
                slide_event = {
                    "type": "SlideAdded",
                    "deck_id": str(deck_id),
                    "slide_id": str(created_slide.id),
                    "slide_order": slide_outline.order,
                    "title": slide_outline.title,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
                await self.event_repo.store_event(deck_id, slide_event)

            await self.uow.commit()

        return slides

    async def _update_deck_status(
        self, deck_id: UUID, status: DeckStatus, message: str
    ):
        """Update deck status and broadcast to clients."""

        async with self.uow:
            deck = await self.deck_repo.get_by_id(deck_id)
            if deck:
                deck.status = status
                deck.updated_at = datetime.now(timezone.utc)
                await self.deck_repo.update(deck)

                # Store status change event
                status_event = {
                    "type": "DeckStatusChanged",
                    "deck_id": str(deck_id),
                    "old_status": deck.status.value if deck.status else None,
                    "new_status": status.value,
                    "message": message,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
                await self.event_repo.store_event(deck_id, status_event)

                await self.uow.commit()

        # Broadcast status change
        try:
            await self.ws_broadcaster.broadcast_to_deck(
                deck_id=str(deck_id),
                message={
                    "type": "DeckStatusChanged",
                    "deck_id": str(deck_id),
                    "status": status.value,
                    "message": message,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
        except Exception as e:
            self._log.exception("ws.broadcast.error", error=str(e))

    async def _enqueue_slide_generation_jobs(self, deck_id: UUID, slides: List[Slide]):
        """Enqueue background jobs for slide content generation."""

        # This would enqueue ARQ jobs for slide content generation
        # For now, just log that jobs would be enqueued
        self._log.info(
            "enqueue.slide_jobs.placeholder", deck_id=str(deck_id), count=len(slides)
        )

        # In a full implementation:
        # for slide in slides:
        #     await self.arq_client.enqueue_job(
        #         "generate_slide_content",
        #         deck_id=str(deck_id),
        #         slide_id=str(slide.id),
        #         primary_template="default.html"
        #     )
