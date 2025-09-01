import time
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

import structlog
from arq import ArqRedis

from app.api.schemas import DeckCreationRequest, Event
from app.core.observability import metrics, trace_async_operation
from app.core.security import html_sanitizer
from app.domain.entities import Deck, DeckEvent, DeckStatus, Slide
from app.domain.exceptions import (
    DeckNotFoundException,
    InvalidDeckStatusException,
    UnauthorizedAccessException,
)
from app.domain.repositories import DeckRepository, EventRepository, SlideRepository
from app.infrastructure.messaging.redis_client import RedisCacheManager, RedisStreamPublisher

logger = structlog.get_logger(__name__)


class DeckService:
    def __init__(
        self,
        deck_repo: DeckRepository,
        slide_repo: SlideRepository,
        event_repo: EventRepository,
        stream_publisher: RedisStreamPublisher,
        cache_manager: RedisCacheManager,
        arq_redis: ArqRedis,
    ) -> None:
        self.deck_repo = deck_repo
        self.slide_repo = slide_repo
        self.event_repo = event_repo
        self.stream_publisher = stream_publisher
        self.cache_manager = cache_manager
        self.arq_redis = arq_redis

    async def create_deck(self, request: DeckCreationRequest, user_id: str) -> Deck:
        """Create a new deck and queue generation job."""
        async with trace_async_operation("create_deck", user_id=user_id, title=request.title):
            start_time = time.time()
            
            try:
                # Create deck entity
                deck = Deck(
                    id=uuid4(),
                    user_id=user_id,
                    title=request.title,
                    status=DeckStatus.PENDING,
                )
                
                # Save to database
                created_deck = await self.deck_repo.create(deck)
                
                # Create initial event
                event = DeckEvent(
                    deck_id=deck.id,
                    version=deck.version,
                    event_type="DeckStarted",
                    payload={
                        "title": request.title,
                        "topic": request.topic,
                        "audience": request.audience,
                        "style": request.style,
                        "slide_count": request.slide_count,
                        "language": request.language,
                        "include_speaker_notes": request.include_speaker_notes,
                    }
                )
                
                await self.event_repo.create(event)
                await self._publish_event(event)
                
                # Queue deck generation job
                await self.arq_redis.enqueue_job(
                    "generate_deck",
                    deck_id=str(deck.id),
                    generation_params={
                        "title": request.title,
                        "topic": request.topic,
                        "audience": request.audience,
                        "style": request.style,
                        "slide_count": request.slide_count,
                        "language": request.language,
                        "include_speaker_notes": request.include_speaker_notes,
                    }
                )
                
                duration = time.time() - start_time
                logger.info(
                    "Deck creation started",
                    deck_id=str(deck.id),
                    user_id=user_id,
                    duration=f"{duration:.2f}s"
                )
                
                return created_deck
                
            except Exception as e:
                logger.error("Failed to create deck", user_id=user_id, error=str(e))
                raise

    async def get_deck(self, deck_id: UUID, user_id: str) -> Deck:
        """Get deck with authorization check."""
        async with trace_async_operation("get_deck", deck_id=str(deck_id), user_id=user_id):
            # Fetch deck first to return 404 when not found
            deck = await self.deck_repo.get_by_id(deck_id)
            if not deck:
                raise DeckNotFoundException(str(deck_id))

            # Check ownership after confirming existence
            if deck.user_id != user_id and not await self.deck_repo.is_owned_by_user(deck_id, user_id):
                raise UnauthorizedAccessException(f"deck:{deck_id}", user_id)

            return deck

    async def get_deck_with_slides(self, deck_id: UUID, user_id: str) -> tuple[Deck, List[Slide]]:
        """Get deck with its slides."""
        async with trace_async_operation("get_deck_with_slides", deck_id=str(deck_id), user_id=user_id):
            deck = await self.get_deck(deck_id, user_id)
            slides = await self.slide_repo.get_by_deck_id(deck_id)
            return deck, slides

    async def list_decks(self, user_id: str, limit: int = 10, offset: int = 0) -> List[Deck]:
        """List user's decks."""
        async with trace_async_operation("list_decks", user_id=user_id):
            return await self.deck_repo.get_by_user_id(user_id, limit, offset)

    async def cancel_deck_generation(self, deck_id: UUID, user_id: str) -> Deck:
        """Cancel ongoing deck generation."""
        async with trace_async_operation("cancel_deck", deck_id=str(deck_id), user_id=user_id):
            # Explicitly fetch to distinguish 404 vs 403
            deck = await self.deck_repo.get_by_id(deck_id)
            if not deck:
                raise DeckNotFoundException(str(deck_id))
            if deck.user_id != user_id and not await self.deck_repo.is_owned_by_user(deck_id, user_id):
                raise UnauthorizedAccessException(f"deck:{deck_id}", user_id)
            
            if not deck.can_be_cancelled():
                raise InvalidDeckStatusException(
                    str(deck_id), 
                    deck.status.value, 
                    "PENDING, PLANNING, or GENERATING"
                )
            
            # Set cancellation flag
            await self.cache_manager.set_cancellation_flag(deck_id)
            
            # Update deck status
            deck.update_status(DeckStatus.CANCELLED)
            updated_deck = await self.deck_repo.update(deck)
            
            # Create and publish cancellation event
            event = DeckEvent(
                deck_id=deck_id,
                version=deck.version,
                event_type="DeckCancelled",
                payload={"reason": "User requested cancellation"}
            )
            
            await self.event_repo.create(event)
            await self._publish_event(event)
            
            logger.info("Deck generation cancelled", deck_id=str(deck_id), user_id=user_id)
            return updated_deck

    async def get_deck_events(self, deck_id: UUID, user_id: str, from_version: int = 0) -> List[DeckEvent]:
        """Get deck events for replay."""
        async with trace_async_operation("get_deck_events", deck_id=str(deck_id), user_id=user_id):
            # Ensure deck exists first
            deck = await self.deck_repo.get_by_id(deck_id)
            if not deck:
                raise DeckNotFoundException(str(deck_id))
            # Check ownership
            if deck.user_id != user_id and not await self.deck_repo.is_owned_by_user(deck_id, user_id):
                raise UnauthorizedAccessException(f"deck:{deck_id}", user_id)

            return await self.event_repo.get_by_deck_id(deck_id, from_version)

    async def _publish_event(self, event: DeckEvent) -> None:
        """Publish event to Redis streams."""
        try:
            api_event = Event(
                event_type=event.event_type,
                deck_id=event.deck_id,
                version=event.version,
                timestamp=event.created_at,
                payload=event.payload
            )
            await self.stream_publisher.publish_event(api_event)
        except Exception as e:
            logger.error("Failed to publish event", event_type=event.event_type, error=str(e))


class SlideService:
    def __init__(
        self,
        slide_repo: SlideRepository,
        deck_repo: DeckRepository,
        event_repo: EventRepository,
        stream_publisher: RedisStreamPublisher,
        arq_redis: ArqRedis,
    ) -> None:
        self.slide_repo = slide_repo
        self.deck_repo = deck_repo
        self.event_repo = event_repo
        self.stream_publisher = stream_publisher
        self.arq_redis = arq_redis

    async def get_slide(self, slide_id: UUID, user_id: str) -> Slide:
        """Get slide with authorization check."""
        async with trace_async_operation("get_slide", slide_id=str(slide_id), user_id=user_id):
            slide = await self.slide_repo.get_by_id(slide_id)
            if not slide:
                raise DeckNotFoundException(str(slide_id))
            
            # Check deck ownership
            if not await self.deck_repo.is_owned_by_user(slide.deck_id, user_id):
                raise UnauthorizedAccessException(f"slide:{slide_id}", user_id)
            
            return slide

    async def update_slide(self, slide_id: UUID, prompt: str, user_id: str) -> None:
        """Queue slide update job."""
        async with trace_async_operation("update_slide", slide_id=str(slide_id), user_id=user_id):
            slide = await self.get_slide(slide_id, user_id)
            deck = await self.deck_repo.get_by_id(slide.deck_id)
            
            if not deck or not deck.can_be_modified():
                raise InvalidDeckStatusException(
                    str(slide.deck_id),
                    deck.status.value if deck else "UNKNOWN",
                    "PENDING, PLANNING, GENERATING, or COMPLETED"
                )
            
            # Queue update job
            await self.arq_redis.enqueue_job(
                "update_slide",
                slide_id=str(slide_id),
                update_prompt=prompt,
                user_id=user_id
            )
            
            logger.info("Slide update queued", slide_id=str(slide_id), user_id=user_id)

    async def add_slide(self, deck_id: UUID, position: int, prompt: str, user_id: str) -> None:
        """Queue slide addition job."""
        async with trace_async_operation("add_slide", deck_id=str(deck_id), user_id=user_id):
            # Check ownership
            if not await self.deck_repo.is_owned_by_user(deck_id, user_id):
                raise UnauthorizedAccessException(f"deck:{deck_id}", user_id)
            
            deck = await self.deck_repo.get_by_id(deck_id)
            if not deck or not deck.can_be_modified():
                raise InvalidDeckStatusException(
                    str(deck_id),
                    deck.status.value if deck else "UNKNOWN",
                    "PENDING, PLANNING, GENERATING, or COMPLETED"
                )
            
            # Queue addition job
            await self.arq_redis.enqueue_job(
                "add_slide",
                deck_id=str(deck_id),
                position=position,
                prompt=prompt,
                user_id=user_id
            )
            
            logger.info("Slide addition queued", deck_id=str(deck_id), position=position, user_id=user_id)

    async def create_slide(
        self,
        deck_id: UUID,
        slide_order: int,
        html_content: str,
        presenter_notes: Optional[str] = None
    ) -> Slide:
        """Create a new slide (internal use by workers)."""
        async with trace_async_operation("create_slide", deck_id=str(deck_id)):
            # Sanitize HTML content
            sanitized_content = html_sanitizer.sanitize(html_content)
            
            slide = Slide(
                id=uuid4(),
                deck_id=deck_id,
                slide_order=slide_order,
                html_content=sanitized_content,
                presenter_notes=presenter_notes
            )
            
            created_slide = await self.slide_repo.create(slide)
            
            # Update deck version and create event
            deck = await self.deck_repo.get_by_id(deck_id)
            if deck:
                deck.increment_version()
                await self.deck_repo.update(deck)
                
                event = DeckEvent(
                    deck_id=deck_id,
                    version=deck.version,
                    event_type="SlideAdded",
                    payload={
                        "slide_id": str(slide.id),
                        "slide_order": slide_order,
                        "title": self._extract_title_from_html(sanitized_content)
                    }
                )
                
                await self.event_repo.create(event)
                await self._publish_event(event)
            
            logger.info("Slide created", slide_id=str(slide.id), deck_id=str(deck_id))
            return created_slide

    async def update_slide_content(
        self,
        slide_id: UUID,
        html_content: str,
        presenter_notes: Optional[str] = None
    ) -> Slide:
        """Update slide content (internal use by workers)."""
        async with trace_async_operation("update_slide_content", slide_id=str(slide_id)):
            slide = await self.slide_repo.get_by_id(slide_id)
            if not slide:
                raise DeckNotFoundException(str(slide_id))
            
            # Sanitize HTML content
            sanitized_content = html_sanitizer.sanitize(html_content)
            
            slide.update_content(sanitized_content, presenter_notes)
            updated_slide = await self.slide_repo.update(slide)
            
            # Update deck version and create event
            deck = await self.deck_repo.get_by_id(slide.deck_id)
            if deck:
                deck.increment_version()
                await self.deck_repo.update(deck)
                
                event = DeckEvent(
                    deck_id=slide.deck_id,
                    version=deck.version,
                    event_type="SlideUpdated",
                    payload={
                        "slide_id": str(slide_id),
                        "slide_order": slide.slide_order,
                        "title": self._extract_title_from_html(sanitized_content)
                    }
                )
                
                await self.event_repo.create(event)
                await self._publish_event(event)
            
            logger.info("Slide updated", slide_id=str(slide_id))
            return updated_slide

    def _extract_title_from_html(self, html_content: str) -> str:
        """Extract title from HTML content."""
        import re
        # Simple regex to extract first heading
        match = re.search(r'<h[1-6][^>]*>(.*?)</h[1-6]>', html_content, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return "Untitled Slide"

    async def _publish_event(self, event: DeckEvent) -> None:
        """Publish event to Redis streams."""
        try:
            api_event = Event(
                event_type=event.event_type,
                deck_id=event.deck_id,
                version=event.version,
                timestamp=event.created_at,
                payload=event.payload
            )
            await self.stream_publisher.publish_event(api_event)
        except Exception as e:
            logger.error("Failed to publish event", event_type=event.event_type, error=str(e))
