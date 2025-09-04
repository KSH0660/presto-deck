"""
Background Job: Generate Slide Content

This job handles generating HTML content for individual slides using LLM.
"""

from uuid import UUID
from datetime import datetime, timezone

from app.data.repositories.slide_repository import SlideRepository
from app.data.repositories.event_repository import EventRepository
from app.infra.messaging.websocket_broadcaster import WebSocketBroadcaster
from app.infra.llm.langchain_client import LangChainClient
from app.infra.config.logging_config import get_logger, bind_context


class GenerateSlideContentJob:
    """
    Background job for generating individual slide HTML content using LLM.

    This runs after deck planning is complete and generates the actual
    HTML content for each slide.
    """

    def __init__(
        self,
        slide_repo: SlideRepository,
        event_repo: EventRepository,
        ws_broadcaster: WebSocketBroadcaster,
        llm_client: LangChainClient,
    ):
        self.slide_repo = slide_repo
        self.event_repo = event_repo
        self.ws_broadcaster = ws_broadcaster
        self.llm_client = llm_client
        self._log = get_logger("job.generate_slide_content")

    async def execute(
        self,
        slide_id: UUID,
        deck_id: UUID,
        template_filename: str = "content_slide.html",
    ) -> bool:
        """
        Execute slide content generation job.

        Returns:
            bool: True if successful, False otherwise
        """
        bind_context(slide_id=str(slide_id), deck_id=str(deck_id))
        self._log.info("job.start", template=template_filename)

        try:
            # 1. Get slide from repository
            slide = await self.slide_repo.get_by_id(slide_id)
            if not slide:
                raise ValueError(f"Slide {slide_id} not found")

            # 2. Generate HTML content using LLM
            html_content = await self._generate_slide_html(slide, template_filename)

            # 3. Update slide with generated content
            slide.html_content = html_content
            slide.template_filename = template_filename
            await self.slide_repo.update(slide)

            # 4. Publish slide updated event
            await self._publish_slide_updated_event(slide)

            self._log.info("job.completed", content_length=len(html_content))
            return True

        except Exception as e:
            self._log.error("job.failed", error=str(e), exc_info=True)
            await self._publish_slide_failed_event(slide_id, deck_id, str(e))
            return False

    async def _generate_slide_html(self, slide, template_filename: str) -> str:
        """Generate HTML content for a slide using LLM."""
        self._log.info("job.llm.start", title=slide.title)

        # TODO: Implement LLM call for slide HTML generation
        # For now, return a placeholder
        html_content = f"""
        <div class="slide">
            <h1>{slide.title}</h1>
            <div class="content">
                <p>{slide.content_outline}</p>
            </div>
            <div class="notes">
                <p>{slide.presenter_notes}</p>
            </div>
        </div>
        """

        self._log.info("job.llm.completed", content_length=len(html_content))
        return html_content.strip()

    async def _publish_slide_updated_event(self, slide):
        """Publish event when slide content is generated."""
        event_data = {
            "type": "SlideContentGenerated",
            "deck_id": str(slide.deck_id),
            "slide_id": str(slide.id),
            "title": slide.title,
            "is_complete": slide.is_complete(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": 1,
        }

        await self.event_repo.store_event(slide.deck_id, event_data)
        await self.ws_broadcaster.broadcast_to_deck(slide.deck_id, event_data)

    async def _publish_slide_failed_event(
        self, slide_id: UUID, deck_id: UUID, error: str
    ):
        """Publish event when slide generation fails."""
        event_data = {
            "type": "SlideGenerationFailed",
            "deck_id": str(deck_id),
            "slide_id": str(slide_id),
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": 1,
        }

        await self.event_repo.store_event(deck_id, event_data)
        await self.ws_broadcaster.broadcast_to_deck(deck_id, event_data)
