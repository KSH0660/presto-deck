"""
Use Case: Write Slide Content in HTML

This use case handles:
1. Validating slide exists and is ready for content generation
2. Using LLM to generate HTML content based on outline and template
3. Updating slide with HTML content
4. Publishing SlideCompleted event
5. Checking if all slides are complete to mark deck as COMPLETED
"""

from typing import Dict, Any
from uuid import UUID
from datetime import datetime

from app.domain_core.entities.slide import Slide
from app.domain_core.value_objects.deck_status import DeckStatus
from app.domain_core.validators.slide_validators import SlideValidators
from app.data.repositories.deck_repository import DeckRepository
from app.data.repositories.slide_repository import SlideRepository
from app.data.repositories.event_repository import EventRepository
from app.infra.messaging.websocket_broadcaster import WebSocketBroadcaster
from app.infra.llm.langchain_client import LangChainClient
from app.application.unit_of_work import UnitOfWork


class WriteSlideContentUseCase:
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

    async def execute(
        self, deck_id: UUID, slide_id: UUID, content_outline: str, template_type: str
    ) -> Dict[str, Any]:
        """
        Execute slide content generation.

        Args:
            deck_id: The deck containing the slide
            slide_id: The slide to generate content for
            content_outline: The content outline to expand
            template_type: The template to use for styling

        Returns:
            Dict with slide_id and completion status
        """
        # 1. Validate slide exists and belongs to deck
        slide = await self.slide_repo.get_by_id(slide_id)
        if not slide:
            raise ValueError(f"Slide {slide_id} not found")

        if slide.deck_id != deck_id:
            raise ValueError(f"Slide {slide_id} does not belong to deck {deck_id}")

        if slide.html_content:
            raise ValueError(f"Slide {slide_id} already has content")

        # 2. Domain validation
        SlideValidators.validate_content_outline(content_outline)

        # 3. Generate HTML content using LLM
        html_content = await self._generate_html_content(
            content_outline, template_type, slide.title, slide.presenter_notes
        )

        # 4. Validate and sanitize HTML
        sanitized_html = SlideValidators.sanitize_html_content(html_content)

        # 5. Update slide in transaction
        async with self.uow:
            slide.html_content = sanitized_html
            slide.updated_at = datetime.utcnow()
            await self.slide_repo.update(slide)

            # Store slide completed event
            slide_event = {
                "type": "SlideCompleted",
                "deck_id": str(deck_id),
                "slide_id": str(slide_id),
                "slide_order": slide.order,
                "timestamp": datetime.utcnow().isoformat(),
            }
            await self.event_repo.store_event(deck_id, slide_event)

            await self.uow.commit()

        # 6. Check if all slides are complete
        deck_completed = await self._check_and_complete_deck(deck_id)

        # 7. Side effects after commit
        await self._trigger_side_effects(deck_id, slide, deck_completed)

        return {
            "deck_id": str(deck_id),
            "slide_id": str(slide_id),
            "slide_order": slide.order,
            "status": "completed",
            "deck_completed": deck_completed,
        }

    async def _generate_html_content(
        self, outline: str, template_type: str, title: str, presenter_notes: str
    ) -> str:
        """Use LLM to generate HTML content for the slide."""
        html_prompt = f"""
        Generate professional HTML content for a presentation slide with these requirements:

        Title: {title}
        Content Outline: {outline}
        Template Style: {template_type}
        Presenter Notes: {presenter_notes}

        Requirements:
        - Use semantic HTML5 elements
        - Include appropriate CSS classes for styling
        - Make content engaging and visual
        - Include bullet points, headings, and structure
        - Keep it concise but comprehensive
        - No external scripts or unsafe content

        Return only the HTML content (no <html>, <head>, or <body> tags).
        """

        response = await self.llm_client.generate_text(html_prompt)
        return response.strip()

    async def _check_and_complete_deck(self, deck_id: UUID) -> bool:
        """Check if all slides are complete and mark deck as completed if so."""
        incomplete_slides = await self.slide_repo.count_incomplete_slides(deck_id)

        if incomplete_slides == 0:
            # All slides complete - mark deck as completed
            async with self.uow:
                deck = await self.deck_repo.get_by_id(deck_id)
                if deck and deck.status == DeckStatus.GENERATING:
                    deck.mark_as_completed()
                    await self.deck_repo.update(deck)

                    # Store deck completed event
                    completion_event = {
                        "type": "DeckCompleted",
                        "deck_id": str(deck_id),
                        "total_slides": await self.slide_repo.count_slides(deck_id),
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                    await self.event_repo.store_event(deck_id, completion_event)

                    await self.uow.commit()
                    return True

        return False

    async def _trigger_side_effects(
        self, deck_id: UUID, slide: Slide, deck_completed: bool
    ):
        """Handle side effects after successful slide completion."""
        try:
            # 1. Broadcast slide completion
            await self.ws_broadcaster.broadcast_to_deck(
                deck_id=str(deck_id),
                message={
                    "type": "SlideCompleted",
                    "deck_id": str(deck_id),
                    "slide_id": str(slide.id),
                    "slide_order": slide.order,
                    "title": slide.title,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            # 2. If deck is complete, broadcast completion
            if deck_completed:
                await self.ws_broadcaster.broadcast_to_deck(
                    deck_id=str(deck_id),
                    message={
                        "type": "DeckCompleted",
                        "deck_id": str(deck_id),
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

        except Exception as e:
            print(f"Side effect error for slide {slide.id}: {e}")
            # In production: logger.error("Slide completion side effect failed")
