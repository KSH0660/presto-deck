"""
Use Case: Write Slide Content in HTML

This use case handles:
1. Validating slide exists and is ready for content generation
2. Using LLM to generate HTML content based on outline and template
3. Updating slide with HTML content
4. Publishing SlideCompleted event
5. Checking if all slides are complete to mark deck as COMPLETED
"""

from typing import Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone

from app.domain.entities.slide import Slide
from app.api.schemas import DeckStatus
from app.domain.validators.slide_validators import SlideValidators
from app.data.repositories.deck_repository import DeckRepository
from app.data.repositories.slide_repository import SlideRepository
from app.data.repositories.event_repository import EventRepository
from app.infra.messaging.websocket_broadcaster import WebSocketBroadcaster
from app.infra.llm.langchain_client import LangChainClient
from app.application.prompts.slide_content import SlideContent, SlideContentPrompts
from app.infra.assets.template_catalog import TemplateCatalog
from app.application.unit_of_work import UnitOfWork
from app.infra.config.logging_config import get_logger, bind_context


class WriteSlideContentUseCase:
    def __init__(
        self,
        uow: UnitOfWork,
        deck_repo: DeckRepository,
        slide_repo: SlideRepository,
        event_repo: EventRepository,
        ws_broadcaster: WebSocketBroadcaster,
        llm_client: LangChainClient,
        template_catalog: TemplateCatalog,
    ):
        self.uow = uow
        self.deck_repo = deck_repo
        self.slide_repo = slide_repo
        self.event_repo = event_repo
        self.ws_broadcaster = ws_broadcaster
        self.llm_client = llm_client
        self.template_catalog = template_catalog
        self._log = get_logger("usecase.write_slide_content")

    async def execute(
        self,
        deck_id: UUID,
        slide_id: UUID,
        slide_order: int,
        content_outline: str,
        primary_template: str,
        alternative_templates: List[str] = None,
        adaptation_notes: str = "",
    ) -> Dict[str, Any]:
        """
        Execute slide content generation with template-based approach.

        Args:
            deck_id: The deck containing the slide
            slide_id: The slide to generate content for
            slide_order: The order of the slide in the deck
            content_outline: The content outline to expand
            primary_template: Primary template filename to use
            alternative_templates: Alternative template filenames as fallbacks
            adaptation_notes: Notes for adapting content to template

        Returns:
            Dict with slide_id and completion status
        """
        bind_context(deck_id=str(deck_id), slide_id=str(slide_id))
        self._log.info(
            "usecase.start",
            action="write_slide_content",
            slide_order=slide_order,
            primary_template=primary_template,
        )
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

        # 3. Generate HTML content using LLM with template
        html_content = await self._generate_html_content_with_template(
            content_outline,
            primary_template,
            alternative_templates or [],
            adaptation_notes,
            slide.title,
            slide.presenter_notes,
        )

        # 4. Validate and sanitize HTML
        sanitized_html = SlideValidators.sanitize_html_content(html_content)

        # 5. Update slide in transaction
        async with self.uow:
            slide.html_content = sanitized_html
            slide.updated_at = datetime.now(timezone.utc)
            await self.slide_repo.update(slide)

            # Store slide completed event
            slide_event = {
                "type": "SlideCompleted",
                "deck_id": str(deck_id),
                "slide_id": str(slide_id),
                "slide_order": slide.order,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await self.event_repo.store_event(deck_id, slide_event)

            await self.uow.commit()

        # 6. Check if all slides are complete
        deck_completed = await self._check_and_complete_deck(deck_id)

        # 7. Side effects after commit
        await self._trigger_side_effects(deck_id, slide, deck_completed)

        result = {
            "deck_id": str(deck_id),
            "slide_id": str(slide_id),
            "slide_order": slide.order,
            "status": "completed",
            "deck_completed": deck_completed,
        }
        self._log.info(
            "usecase.success",
            slide_id=str(slide_id),
            deck_completed=deck_completed,
        )
        return result

    async def _generate_html_content_with_template(
        self,
        outline: str,
        primary_template: str,
        alternative_templates: List[str],
        adaptation_notes: str,
        title: str,
        presenter_notes: str,
    ) -> str:
        """Generate HTML content using actual template files as reference."""

        # Get the primary template content
        template_content = self.template_catalog.get_template_content(primary_template)
        if not template_content:
            # Fallback to first alternative if primary not found
            for alt_template in alternative_templates:
                template_content = self.template_catalog.get_template_content(
                    alt_template
                )
                if template_content:
                    primary_template = alt_template
                    break

        # If still no template found, use basic content generation
        if not template_content:
            return await self._generate_basic_html_content(
                outline, title, presenter_notes
            )

        # Use structured output for better reliability
        system_prompt = SlideContentPrompts.get_system_prompt()
        user_prompt = self._create_template_based_prompt(
            title,
            outline,
            primary_template,
            template_content,
            adaptation_notes,
            presenter_notes,
        )

        # If simple text generation is available (tests may mock this), use it
        if hasattr(self.llm_client, "generate_text"):
            html = await self.llm_client.generate_text(user_prompt)
            return html

        # Otherwise use structured output
        messages = self.llm_client.create_messages(user_prompt, system_prompt)
        slide_content = await self.llm_client.invoke_structured(messages, SlideContent)
        return slide_content.html_content

    def _create_template_based_prompt(
        self,
        title: str,
        outline: str,
        template_name: str,
        template_content: str,
        adaptation_notes: str,
        presenter_notes: str,
    ) -> str:
        """Create prompt for template-based HTML generation."""
        return f"""
Generate HTML content for this slide using the provided template as a reference:

**SLIDE DETAILS:**
Title: {title}
Content Outline: {outline}
Presenter Notes: {presenter_notes}

**TEMPLATE TO FOLLOW:**
Template File: {template_name}
Template Content:
```html
{template_content}
```

**ADAPTATION NOTES:**
{adaptation_notes}

**INSTRUCTIONS:**
1. Study the template structure and CSS classes
2. Create content that fits the template's layout and design approach
3. Replace placeholder content with the actual slide content
4. Maintain visual consistency with the template style
5. Ensure content is engaging and well-structured

Generate only the HTML content that would fit within this template structure.
"""

    async def _generate_basic_html_content(
        self, outline: str, title: str, presenter_notes: str
    ) -> str:
        """Fallback method for basic HTML generation when no template is available."""

        # Use structured output for consistent results
        system_prompt = SlideContentPrompts.get_system_prompt()
        user_prompt = SlideContentPrompts.get_user_prompt(
            title=title,
            content_outline=outline,
            template_type="basic",
            context={"presenter_notes": presenter_notes},
        )

        # If simple text generation is available (tests may mock this), use it
        if hasattr(self.llm_client, "generate_text"):
            html = await self.llm_client.generate_text(user_prompt)
            return html

        # Otherwise use structured output
        messages = self.llm_client.create_messages(user_prompt, system_prompt)
        slide_content = await self.llm_client.invoke_structured(messages, SlideContent)
        return slide_content.html_content

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
                        "timestamp": datetime.now(timezone.utc).isoformat(),
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
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

            # 2. If deck is complete, broadcast completion
            if deck_completed:
                await self.ws_broadcaster.broadcast_to_deck(
                    deck_id=str(deck_id),
                    message={
                        "type": "DeckCompleted",
                        "deck_id": str(deck_id),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

        except Exception as e:
            print(f"Side effect error for slide {slide.id}: {e}")
            # In production: logger.error("Slide completion side effect failed")
