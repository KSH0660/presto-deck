"""
Use Case: Select Template

This use case handles:
1. Validating deck has a completed plan
2. Processing LLM-generated plan to identify best template
3. Updating deck with template selection
4. Enqueueing slide content generation job
5. Publishing PlanCompleted and TemplateSelected events
"""

from typing import Dict, Any, List
from uuid import UUID
from datetime import datetime

from app.domain_core.entities.slide import Slide
from app.domain_core.value_objects.deck_status import DeckStatus
from app.domain_core.value_objects.template_type import TemplateType
from app.domain_core.validators.deck_validators import DeckValidators
from app.data.repositories.deck_repository import DeckRepository
from app.data.repositories.slide_repository import SlideRepository
from app.data.repositories.event_repository import EventRepository
from app.infra.messaging.arq_client import ARQClient
from app.infra.messaging.websocket_broadcaster import WebSocketBroadcaster
from app.infra.llm.langchain_client import LangChainClient
from app.application.unit_of_work import UnitOfWork


class SelectTemplateUseCase:
    def __init__(
        self,
        uow: UnitOfWork,
        deck_repo: DeckRepository,
        slide_repo: SlideRepository,
        event_repo: EventRepository,
        arq_client: ARQClient,
        ws_broadcaster: WebSocketBroadcaster,
        llm_client: LangChainClient,
    ):
        self.uow = uow
        self.deck_repo = deck_repo
        self.slide_repo = slide_repo
        self.event_repo = event_repo
        self.arq_client = arq_client
        self.ws_broadcaster = ws_broadcaster
        self.llm_client = llm_client

    async def execute(self, deck_id: UUID, deck_plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute template selection based on deck plan.

        Args:
            deck_id: The deck to update
            deck_plan: LLM-generated plan with slides structure

        Returns:
            Dict with selected template and slide structure
        """
        # 1. Validate deck exists and is in correct state
        deck = await self.deck_repo.get_by_id(deck_id)
        if not deck:
            raise ValueError(f"Deck {deck_id} not found")

        if deck.status != DeckStatus.PLANNING:
            raise ValueError(
                f"Deck must be in PLANNING status, currently {deck.status}"
            )

        # 2. Domain validation
        DeckValidators.validate_deck_plan(deck_plan)

        # 3. Select best template using LLM
        selected_template = await self._select_best_template(
            deck_plan, deck.style_preferences
        )

        # 4. Create slide entities from plan
        slides = self._create_slide_entities(
            deck_id, deck_plan["slides"], selected_template
        )

        # 5. Transaction boundary
        async with self.uow:
            # Update deck status and template
            deck.status = DeckStatus.GENERATING
            deck.template_type = selected_template
            deck.updated_at = datetime.utcnow()
            await self.deck_repo.update(deck)

            # Create slide records
            for slide in slides:
                await self.slide_repo.create(slide)

            # Store events
            plan_event = {
                "type": "PlanCompleted",
                "deck_id": str(deck_id),
                "plan": deck_plan,
                "timestamp": datetime.utcnow().isoformat(),
                "version": 2,
            }
            await self.event_repo.store_event(deck_id, plan_event)

            template_event = {
                "type": "TemplateSelected",
                "deck_id": str(deck_id),
                "template": selected_template.value,
                "slide_count": len(slides),
                "timestamp": datetime.utcnow().isoformat(),
                "version": 3,
            }
            await self.event_repo.store_event(deck_id, template_event)

            await self.uow.commit()

        # 6. Side effects after commit
        await self._trigger_side_effects(deck_id, slides, selected_template)

        return {
            "deck_id": str(deck_id),
            "template": selected_template.value,
            "slide_count": len(slides),
            "status": DeckStatus.GENERATING.value,
        }

    async def _select_best_template(
        self, deck_plan: Dict[str, Any], style_preferences: Dict[str, Any]
    ) -> TemplateType:
        """Use LLM to select the best template for the deck."""
        template_prompt = f"""
        Based on this deck plan and style preferences, select the best template:

        Plan: {deck_plan}
        Style: {style_preferences}

        Available templates: {[t.value for t in TemplateType]}

        Return only the template name.
        """

        response = await self.llm_client.generate_text(template_prompt)
        template_name = response.strip().lower()

        # Map response to enum
        for template_type in TemplateType:
            if template_type.value.lower() == template_name:
                return template_type

        # Default fallback
        return TemplateType.PROFESSIONAL

    def _create_slide_entities(
        self, deck_id: UUID, slide_plans: List[Dict[str, Any]], template: TemplateType
    ) -> List[Slide]:
        """Create slide entities from plan data."""
        slides = []
        for i, slide_plan in enumerate(slide_plans):
            slide = Slide(
                id=None,  # Will be set by repository
                deck_id=deck_id,
                order=i + 1,
                title=slide_plan.get("title", f"Slide {i + 1}"),
                content_outline=slide_plan.get("content", ""),
                html_content=None,  # Will be generated later
                presenter_notes=slide_plan.get("notes", ""),
                template_type=template,
                created_at=datetime.utcnow(),
            )
            slides.append(slide)

        return slides

    async def _trigger_side_effects(
        self, deck_id: UUID, slides: List[Slide], template: TemplateType
    ):
        """Handle side effects after successful template selection."""
        try:
            # 1. Enqueue slide content generation jobs (one per slide)
            job_ids = []
            for slide in slides:
                job_id = await self.arq_client.enqueue(
                    "generate_slide_content",
                    deck_id=str(deck_id),
                    slide_id=str(slide.id),
                    slide_order=slide.order,
                    content_outline=slide.content_outline,
                    template=template.value,
                )
                job_ids.append(job_id)

            # 2. Broadcast template selection to WebSocket clients
            await self.ws_broadcaster.broadcast_to_deck(
                deck_id=str(deck_id),
                message={
                    "type": "TemplateSelected",
                    "deck_id": str(deck_id),
                    "template": template.value,
                    "slide_count": len(slides),
                    "job_ids": job_ids,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        except Exception as e:
            print(f"Side effect error for deck {deck_id}: {e}")
            # In production: logger.error("Template selection side effect failed")
