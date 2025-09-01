import time
from typing import Any, Dict
from uuid import UUID

import structlog
from arq import ArqRedis

from app.api.schemas import Event
from app.core.observability import metrics
from app.core.security import html_sanitizer
from app.domain.entities import Deck, DeckEvent, DeckStatus, Slide
from app.domain.exceptions import DeckNotFoundException, DeckGenerationException
from app.infrastructure.db.database import Database
from app.infrastructure.db.repositories import (
    PostgresDeckRepository,
    PostgresEventRepository,
    PostgresSlideRepository,
)
from app.infrastructure.llm.client import LLMClient
from app.infrastructure.messaging.redis_client import (
    RedisCacheManager,
    RedisStreamPublisher,
)

logger = structlog.get_logger(__name__)


async def generate_deck(ctx: Dict[str, Any], deck_id: str, generation_params: Dict[str, Any]) -> None:
    """Main deck generation task."""
    start_time = time.time()
    deck_uuid = UUID(deck_id)
    
    # Get dependencies from context
    database: Database = ctx["database"]
    redis_client = ctx["redis_client"]
    llm_client: LLMClient = ctx["llm_client"]
    
    stream_publisher = RedisStreamPublisher(redis_client)
    cache_manager = RedisCacheManager(redis_client)
    
    logger.info("Starting deck generation", deck_id=deck_id)
    
    try:
        async with database.session() as session:
            deck_repo = PostgresDeckRepository(session)
            slide_repo = PostgresSlideRepository(session)
            event_repo = PostgresEventRepository(session)
            
            # Check if generation was cancelled
            if await cache_manager.check_cancellation_flag(deck_uuid):
                logger.info("Deck generation was cancelled", deck_id=deck_id)
                return
            
            # Get deck and check if already processed
            deck = await deck_repo.get_by_id(deck_uuid)
            if not deck:
                raise DeckNotFoundException(deck_id)
            
            if deck.status not in {DeckStatus.PENDING}:
                logger.warning("Deck not in pending status, skipping", deck_id=deck_id, status=deck.status)
                return
            
            # Update status to PLANNING
            deck.update_status(DeckStatus.PLANNING)
            await deck_repo.update(deck)
            
            # Generate deck plan
            logger.info("Generating deck plan", deck_id=deck_id)
            
            deck_plan = await llm_client.generate_deck_plan(
                title=generation_params["title"],
                topic=generation_params["topic"],
                audience=generation_params.get("audience"),
                slide_count=generation_params.get("slide_count", 5),
                style=generation_params.get("style", "professional"),
                language=generation_params.get("language", "en")
            )
            
            # Update deck with plan
            deck.update_plan(deck_plan.dict())
            deck.update_status(DeckStatus.GENERATING)
            await deck_repo.update(deck)
            
            # Create and publish plan updated event
            plan_event = DeckEvent(
                deck_id=deck_uuid,
                version=deck.version,
                event_type="PlanUpdated",
                payload={
                    "total_slides": deck_plan.total_slides,
                    "estimated_duration": deck_plan.estimated_duration,
                    "slide_titles": [slide["title"] for slide in deck_plan.slides]
                }
            )
            await event_repo.create(plan_event)
            await _publish_event(stream_publisher, plan_event)
            
            # Generate slides one by one
            logger.info("Starting slide generation", deck_id=deck_id, total_slides=deck_plan.total_slides)
            
            for slide_info in deck_plan.slides:
                # Check cancellation before each slide
                if await cache_manager.check_cancellation_flag(deck_uuid):
                    logger.info("Deck generation cancelled during slide creation", deck_id=deck_id)
                    await _mark_deck_as_cancelled(deck_repo, event_repo, stream_publisher, deck_uuid)
                    return
                
                try:
                    await _generate_single_slide(
                        llm_client=llm_client,
                        slide_repo=slide_repo,
                        deck_repo=deck_repo,
                        event_repo=event_repo,
                        stream_publisher=stream_publisher,
                        deck_uuid=deck_uuid,
                        slide_info=slide_info,
                        deck_context={
                            "title": generation_params["title"],
                            "topic": generation_params["topic"],
                            "audience": generation_params.get("audience", "General"),
                        },
                        include_speaker_notes=generation_params.get("include_speaker_notes", True)
                    )
                    
                except Exception as e:
                    logger.error("Failed to generate slide", deck_id=deck_id, slide=slide_info, error=str(e))
                    await _mark_deck_as_failed(
                        deck_repo, event_repo, stream_publisher, deck_uuid, f"Slide generation failed: {e}"
                    )
                    return
            
            # Mark deck as completed
            deck = await deck_repo.get_by_id(deck_uuid)
            if deck:
                deck.update_status(DeckStatus.COMPLETED)
                await deck_repo.update(deck)
                
                completion_event = DeckEvent(
                    deck_id=deck_uuid,
                    version=deck.version,
                    event_type="DeckCompleted",
                    payload={
                        "total_slides": deck_plan.total_slides,
                        "generation_duration": time.time() - start_time
                    }
                )
                await event_repo.create(completion_event)
                await _publish_event(stream_publisher, completion_event)
            
            # Clear cancellation flag if set
            await cache_manager.clear_cancellation_flag(deck_uuid)
            
            duration = time.time() - start_time
            metrics.record_deck_generation("completed", duration)
            
            logger.info(
                "Deck generation completed",
                deck_id=deck_id,
                duration=f"{duration:.2f}s",
                slides=deck_plan.total_slides
            )
            
    except Exception as e:
        logger.error("Deck generation failed", deck_id=deck_id, error=str(e))
        
        try:
            async with database.session() as session:
                deck_repo = PostgresDeckRepository(session)
                event_repo = PostgresEventRepository(session)
                await _mark_deck_as_failed(deck_repo, event_repo, stream_publisher, deck_uuid, str(e))
        except Exception as cleanup_error:
            logger.error("Failed to mark deck as failed", deck_id=deck_id, error=str(cleanup_error))
        
        metrics.record_deck_generation("failed", time.time() - start_time)
        raise


async def generate_slide(ctx: Dict[str, Any], slide_id: str, slide_info: Dict[str, Any]) -> None:
    """Generate content for a specific slide."""
    logger.info("Generating slide content", slide_id=slide_id)
    
    # This would be used for individual slide generation requests
    # Implementation similar to _generate_single_slide but as a standalone task


async def update_slide(ctx: Dict[str, Any], slide_id: str, update_prompt: str, user_id: str) -> None:
    """Update slide content based on user prompt."""
    slide_uuid = UUID(slide_id)
    
    # Get dependencies
    database: Database = ctx["database"]
    redis_client = ctx["redis_client"]
    llm_client: LLMClient = ctx["llm_client"]
    
    stream_publisher = RedisStreamPublisher(redis_client)
    
    logger.info("Updating slide content", slide_id=slide_id, user_id=user_id)
    
    try:
        async with database.session() as session:
            slide_repo = PostgresSlideRepository(session)
            deck_repo = PostgresDeckRepository(session)
            event_repo = PostgresEventRepository(session)
            
            # Get slide
            slide = await slide_repo.get_by_id(slide_uuid)
            if not slide:
                raise DeckNotFoundException(slide_id)
            
            # Get deck context
            deck = await deck_repo.get_by_id(slide.deck_id)
            if not deck:
                raise DeckNotFoundException(str(slide.deck_id))
            
            # Generate updated content
            updated_content = await llm_client.update_slide_content(
                current_content=slide.html_content,
                update_prompt=update_prompt,
                slide_context={
                    "deck_title": deck.title,
                    "slide_number": slide.slide_order,
                    "deck_plan": deck.deck_plan
                }
            )
            
            # Sanitize and update slide
            sanitized_content = html_sanitizer.sanitize(updated_content.html_content)
            slide.update_content(sanitized_content, updated_content.presenter_notes)
            await slide_repo.update(slide)
            
            # Update deck version and create event
            deck.increment_version()
            await deck_repo.update(deck)
            
            update_event = DeckEvent(
                deck_id=slide.deck_id,
                version=deck.version,
                event_type="SlideUpdated",
                payload={
                    "slide_id": slide_id,
                    "slide_order": slide.slide_order,
                    "title": updated_content.title,
                    "updated_by": user_id
                }
            )
            await event_repo.create(update_event)
            await _publish_event(stream_publisher, update_event)
            
            logger.info("Slide content updated", slide_id=slide_id, user_id=user_id)
            
    except Exception as e:
        logger.error("Failed to update slide", slide_id=slide_id, error=str(e))
        raise


async def cleanup_cancelled_decks(ctx: Dict[str, Any]) -> None:
    """Periodic cleanup of cancelled deck resources."""
    database: Database = ctx["database"]
    redis_client = ctx["redis_client"]
    
    logger.info("Starting cancelled deck cleanup")
    
    try:
        async with database.session() as session:
            deck_repo = PostgresDeckRepository(session)
            
            # Find decks that have been cancelled for more than 1 hour
            # This would require additional query methods
            # For now, just log the cleanup attempt
            
            logger.info("Cancelled deck cleanup completed")
            
    except Exception as e:
        logger.error("Cancelled deck cleanup failed", error=str(e))


# Helper functions

async def _generate_single_slide(
    llm_client: LLMClient,
    slide_repo: PostgresSlideRepository,
    deck_repo: PostgresDeckRepository,
    event_repo: PostgresEventRepository,
    stream_publisher: RedisStreamPublisher,
    deck_uuid: UUID,
    slide_info: Dict[str, Any],
    deck_context: Dict[str, Any],
    include_speaker_notes: bool = True
) -> None:
    """Generate a single slide."""
    slide_number = slide_info["slide_number"]
    
    logger.info("Generating slide", deck_id=str(deck_uuid), slide_number=slide_number)
    
    # Generate slide content using LLM
    slide_content = await llm_client.generate_slide_content(
        slide_info=slide_info,
        deck_context=deck_context,
        slide_number=slide_number,
        include_speaker_notes=include_speaker_notes
    )
    
    # Sanitize HTML content
    sanitized_content = html_sanitizer.sanitize(slide_content.html_content)
    
    # Create slide in database
    slide = Slide(
        deck_id=deck_uuid,
        slide_order=slide_number,
        html_content=sanitized_content,
        presenter_notes=slide_content.presenter_notes
    )
    
    await slide_repo.create(slide)
    
    # Update deck version
    deck = await deck_repo.get_by_id(deck_uuid)
    if deck:
        deck.increment_version()
        await deck_repo.update(deck)
        
        # Create and publish slide added event
        slide_event = DeckEvent(
            deck_id=deck_uuid,
            version=deck.version,
            event_type="SlideAdded",
            payload={
                "slide_id": str(slide.id),
                "slide_order": slide_number,
                "title": slide_content.title
            }
        )
        await event_repo.create(slide_event)
        await _publish_event(stream_publisher, slide_event)
    
    logger.info(
        "Slide generated successfully",
        deck_id=str(deck_uuid),
        slide_number=slide_number,
        slide_id=str(slide.id)
    )


async def _mark_deck_as_failed(
    deck_repo: PostgresDeckRepository,
    event_repo: PostgresEventRepository,
    stream_publisher: RedisStreamPublisher,
    deck_uuid: UUID,
    reason: str
) -> None:
    """Mark deck as failed and publish event."""
    deck = await deck_repo.get_by_id(deck_uuid)
    if deck:
        deck.update_status(DeckStatus.FAILED)
        await deck_repo.update(deck)
        
        failure_event = DeckEvent(
            deck_id=deck_uuid,
            version=deck.version,
            event_type="DeckFailed",
            payload={"reason": reason}
        )
        await event_repo.create(failure_event)
        await _publish_event(stream_publisher, failure_event)


async def _mark_deck_as_cancelled(
    deck_repo: PostgresDeckRepository,
    event_repo: PostgresEventRepository,
    stream_publisher: RedisStreamPublisher,
    deck_uuid: UUID
) -> None:
    """Mark deck as cancelled and publish event."""
    deck = await deck_repo.get_by_id(deck_uuid)
    if deck:
        deck.update_status(DeckStatus.CANCELLED)
        await deck_repo.update(deck)
        
        cancellation_event = DeckEvent(
            deck_id=deck_uuid,
            version=deck.version,
            event_type="DeckCancelled",
            payload={"reason": "Cancelled during generation"}
        )
        await event_repo.create(cancellation_event)
        await _publish_event(stream_publisher, cancellation_event)


async def _publish_event(stream_publisher: RedisStreamPublisher, event: DeckEvent) -> None:
    """Publish event to Redis streams."""
    try:
        api_event = Event(
            event_type=event.event_type,
            deck_id=event.deck_id,
            version=event.version,
            timestamp=event.created_at,
            payload=event.payload
        )
        await stream_publisher.publish_event(api_event)
    except Exception as e:
        logger.error("Failed to publish event", event_type=event.event_type, error=str(e))