"""
Background Job: Generate Deck Plan

This job handles the actual LLM-based deck planning that runs as a background task.
It uses structured output to generate a comprehensive deck plan with slides.
"""

from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone

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


class GenerateDeckPlanJob:
    """
    Background job for generating deck plans using LLM with structured output.

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
        self._log = get_logger("job.generate_deck_plan")

    async def execute(
        self,
        deck_id: UUID,
        user_id: UUID,
        prompt: str,
        style_preferences: Optional[Dict[str, Any]] = None,
    ) -> List[Slide]:
        """
        Execute the deck plan generation job.

        This method:
        1. Validates deck exists and belongs to user
        2. Updates status to PLANNING
        3. Calls LLM to generate structured deck plan
        4. Creates slide entities
        5. Updates status to GENERATING
        6. Publishes events for real-time updates
        """
        bind_context(deck_id=str(deck_id), user_id=str(user_id))
        self._log.info("job.start", action="generate_deck_plan")

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

            # 3. Generate deck plan using LLM
            deck_plan = await self._generate_deck_plan_with_llm(
                prompt, style_preferences
            )

            # 4. Create slides from plan
            slides = await self._create_slides_from_plan(deck_id, deck_plan)

            # 5. Update deck with slide count and status
            await self._finalize_deck_planning(deck_id, len(slides))

            self._log.info("job.completed", slides_created=len(slides))
            return slides

        except Exception as e:
            # Mark deck as failed and re-raise
            await self._update_deck_status(
                deck_id, DeckStatus.FAILED, f"Planning failed: {str(e)}"
            )
            raise

    async def _update_deck_status(
        self, deck_id: UUID, status: DeckStatus, message: str
    ):
        """Update deck status and publish event."""
        deck = await self.deck_repo.get_by_id(deck_id)
        deck.status = status
        await self.deck_repo.update(deck)

        # Publish status update event
        event_data = {
            "type": "DeckStatusUpdated",
            "deck_id": str(deck_id),
            "status": status.value,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": 1,  # Simplified versioning
        }

        await self.event_repo.store_event(deck_id, event_data)
        await self.ws_broadcaster.broadcast_to_deck(deck_id, event_data)

        self._log.info("job.status_updated", status=status.value, message=message)

    async def _generate_deck_plan_with_llm(
        self, prompt: str, style_preferences: Optional[Dict[str, Any]]
    ) -> DeckPlan:
        """Generate structured deck plan using LLM."""
        self._log.info("job.llm.start", prompt_length=len(prompt))

        # Create LLM prompt for deck planning
        planning_prompt = DeckPlanningPrompts.get_user_prompt(
            user_prompt=prompt,
            style_preferences=style_preferences,
        )

        # Create messages for LLM
        messages = self.llm_client.create_messages(
            user_prompt=planning_prompt,
            system_prompt=DeckPlanningPrompts.get_system_prompt(),
        )

        # Call LLM with structured output and retry
        deck_plan = await self.llm_client.invoke_with_retry(
            messages=messages,
            response_model=DeckPlan,
            max_retries=3,
        )

        self._log.info("job.llm.completed", slides_planned=len(deck_plan.slides))
        return deck_plan

    async def _create_slides_from_plan(
        self, deck_id: UUID, deck_plan: DeckPlan
    ) -> List[Slide]:
        """Create slide entities from LLM-generated plan."""
        self._log.info("job.slides.start", count=len(deck_plan.slides))
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

                # Publish slide created event
                event_data = {
                    "type": "SlideCreated",
                    "deck_id": str(deck_id),
                    "slide_id": str(created_slide.id),
                    "order": slide_outline.order,
                    "title": slide_outline.title,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "version": 1,
                }
                await self.event_repo.store_event(deck_id, event_data)

            await self.uow.commit()

        self._log.info("job.slides.completed", slides_created=len(slides))
        return slides

    async def _finalize_deck_planning(self, deck_id: UUID, slide_count: int):
        """Update deck with final slide count and move to next phase."""
        deck = await self.deck_repo.get_by_id(deck_id)
        deck.slide_count = slide_count
        deck.status = DeckStatus.GENERATING  # Move to slide content generation

        await self.deck_repo.update(deck)

        # Publish planning completed event
        event_data = {
            "type": "PlanningCompleted",
            "deck_id": str(deck_id),
            "slide_count": slide_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": 1,
        }

        await self.event_repo.store_event(deck_id, event_data)
        await self.ws_broadcaster.broadcast_to_deck(deck_id, event_data)

        # TODO: Enqueue slide content generation jobs here
        await self._enqueue_slide_generation_jobs(deck_id, slide_count)

    async def _enqueue_slide_generation_jobs(self, deck_id: UUID, slide_count: int):
        """Enqueue individual slide content generation jobs."""
        # This would enqueue ARQ jobs for slide content generation
        self._log.info(
            "job.enqueue.slide_jobs.placeholder",
            deck_id=str(deck_id),
            count=slide_count,
        )
        # TODO: Implement slide content generation job enqueueing
