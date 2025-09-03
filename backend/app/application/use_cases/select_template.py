"""
Use Case: Select Templates from Asset Catalog

This use case handles:
1. Validating deck has a completed plan
2. Using LLM with structured output to match slides to asset templates
3. Selecting up to 3 best template files per slide from catalog
4. Updating deck with template selections
5. Enqueueing slide content generation jobs with specific templates
6. Publishing PlanCompleted and TemplateSelected events
"""

from typing import Dict, Any, List
from uuid import UUID
from datetime import datetime

from app.domain_core.entities.slide import Slide
from app.domain_core.value_objects.deck_status import DeckStatus
from app.domain_core.value_objects.template_selection import DeckTemplateSelections
from app.domain_core.validators.deck_validators import DeckValidators
from app.data.repositories.deck_repository import DeckRepository
from app.data.repositories.slide_repository import SlideRepository
from app.data.repositories.event_repository import EventRepository
from app.infra.messaging.arq_client import ARQClient
from app.infra.messaging.websocket_broadcaster import WebSocketBroadcaster
from app.infra.llm.langchain_client import LangChainClient
from app.infra.assets.template_catalog import TemplateCatalog
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
        template_catalog: TemplateCatalog,
    ):
        self.uow = uow
        self.deck_repo = deck_repo
        self.slide_repo = slide_repo
        self.event_repo = event_repo
        self.arq_client = arq_client
        self.ws_broadcaster = ws_broadcaster
        self.llm_client = llm_client
        self.template_catalog = template_catalog

    async def execute(self, deck_id: UUID, deck_plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute template selection based on deck plan using asset catalog.

        Args:
            deck_id: The deck to update
            deck_plan: LLM-generated plan with slides structure

        Returns:
            Dict with template selections and slide structure
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

        # 3. Select templates using LLM with structured output
        template_selections = await self._select_templates_from_catalog(
            deck_plan, deck.style_preferences
        )

        # 4. Create slide entities with template assignments
        slides = self._create_slides_with_templates(
            deck_id, deck_plan["slides"], template_selections
        )

        # 5. Transaction boundary
        async with self.uow:
            # Update deck status
            deck.status = DeckStatus.GENERATING
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
                "type": "TemplatesSelected",
                "deck_id": str(deck_id),
                "template_selections": template_selections.dict(),
                "slide_count": len(slides),
                "timestamp": datetime.utcnow().isoformat(),
                "version": 3,
            }
            await self.event_repo.store_event(deck_id, template_event)

            await self.uow.commit()

        # 6. Side effects after commit
        await self._trigger_side_effects(deck_id, slides, template_selections)

        return {
            "deck_id": str(deck_id),
            "template_selections": template_selections.dict(),
            "slide_count": len(slides),
            "status": DeckStatus.GENERATING.value,
        }

    async def _select_templates_from_catalog(
        self, deck_plan: Dict[str, Any], style_preferences: Dict[str, Any]
    ) -> DeckTemplateSelections:
        """Use LLM with structured output to select templates from asset catalog."""

        # Get catalog for LLM
        catalog = self.template_catalog.get_catalog_for_llm()

        system_prompt = """You are an expert presentation designer. Your task is to analyze a deck plan and assign the most suitable HTML templates from the available catalog to each slide.

For each slide, consider:
1. The slide's purpose and content type
2. The overall presentation theme and style preferences
3. The flow and narrative of the entire deck

Select the best primary template and up to 2 alternative templates for each slide. Focus on creating visual variety while maintaining coherence."""

        user_prompt = f"""
Analyze this presentation deck plan and assign templates:

DECK PLAN:
{deck_plan}

STYLE PREFERENCES:
{style_preferences}

AVAILABLE TEMPLATES:
{catalog}

Your task:
1. Identify the overall theme/style for this deck
2. For each slide, select the most appropriate primary template
3. Provide 1-2 alternative templates as fallbacks
4. Ensure good visual variety across the deck
5. Consider the logical flow from intro → content → conclusion

Focus on matching slide content to template capabilities.
"""

        # Use structured output
        return await self.llm_client.generate_structured(
            user_prompt, DeckTemplateSelections, system_prompt
        )

    def _create_slides_with_templates(
        self,
        deck_id: UUID,
        slide_plans: List[Dict[str, Any]],
        template_selections: DeckTemplateSelections,
    ) -> List[Slide]:
        """Create slide entities with assigned templates."""
        slides = []

        for i, slide_plan in enumerate(slide_plans):
            # Find corresponding template assignment
            template_assignment = None
            for assignment in template_selections.slide_assignments:
                if assignment.slide_order == i + 1:
                    template_assignment = assignment
                    break

            # Fallback if no assignment found
            primary_template = (
                template_assignment.primary_template
                if template_assignment
                else "content_slide.html"
            )

            slide = Slide(
                id=None,  # Will be set by repository
                deck_id=deck_id,
                order=i + 1,
                title=slide_plan.get("title", f"Slide {i + 1}"),
                content_outline=slide_plan.get("content", ""),
                html_content=None,  # Will be generated later
                presenter_notes=slide_plan.get("notes", ""),
                # Store template filename
                template_filename=primary_template,
                created_at=datetime.utcnow(),
            )
            slides.append(slide)

        return slides

    async def _trigger_side_effects(
        self,
        deck_id: UUID,
        slides: List[Slide],
        template_selections: DeckTemplateSelections,
    ):
        """Handle side effects after successful template selection."""
        try:
            # 1. Enqueue slide content generation jobs with specific templates
            job_ids = []
            for slide in slides:
                # Find template assignment for this slide
                template_assignment = None
                for assignment in template_selections.slide_assignments:
                    if assignment.slide_order == slide.order:
                        template_assignment = assignment
                        break

                job_id = await self.arq_client.enqueue(
                    "generate_slide_content_with_template",
                    deck_id=str(deck_id),
                    slide_id=str(slide.id),
                    slide_order=slide.order,
                    content_outline=slide.content_outline,
                    primary_template=(
                        template_assignment.primary_template
                        if template_assignment
                        else "content_slide.html"
                    ),
                    alternative_templates=(
                        template_assignment.alternative_templates
                        if template_assignment
                        else []
                    ),
                    adaptation_notes=(
                        template_assignment.content_adaptation_notes
                        if template_assignment
                        else ""
                    ),
                )
                job_ids.append(job_id)

            # 2. Broadcast template selections to WebSocket clients
            await self.ws_broadcaster.broadcast_to_deck(
                deck_id=str(deck_id),
                message={
                    "type": "TemplatesSelected",
                    "deck_id": str(deck_id),
                    "deck_theme": template_selections.deck_theme,
                    "slide_count": len(slides),
                    "template_usage": template_selections.template_usage_summary,
                    "job_ids": job_ids,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        except Exception as e:
            print(f"Side effect error for deck {deck_id}: {e}")
            # In production: logger.error("Template selection side effect failed")
