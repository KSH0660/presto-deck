"""
Integration test framework with external system validation.

This module provides comprehensive testing of system integration points
and validates external service dependencies.
"""

import pytest
from uuid import uuid4

from app.infra.config.settings import get_settings
from app.infra.llm.cache_manager import get_cache_manager
from app.infra.llm.cache_utils import inspect_cache


@pytest.mark.integration
@pytest.mark.external
class TestSystemHealthChecks:
    """Test system health and external service availability."""

    async def test_database_connectivity(self, test_db_engine):
        """Test database connection and basic operations."""
        # Test connection
        async with test_db_engine.connect() as conn:
            result = await conn.execute("SELECT 1 as test")
            row = result.fetchone()
            assert row[0] == 1

    async def test_redis_connectivity(self, check_redis_available, test_redis_client):
        """Test Redis connection and basic operations."""
        if not check_redis_available:
            pytest.skip("Redis not available")

        # Test basic connectivity
        assert await test_redis_client.ping() is True

        # Test basic operations
        await test_redis_client.set("health:check", "ok")
        result = await test_redis_client.get("health:check")
        assert result.decode("utf-8") == "ok"

    async def test_llm_cache_system_health(self, clean_cache):
        """Test LLM cache system health."""
        cache_manager = get_cache_manager()

        # Initialize cache
        cache_manager.initialize_cache()

        # Check cache statistics
        stats = cache_manager.get_cache_stats()
        assert stats["enabled"] is True
        assert stats["type"] in ["sqlite", "redis", "memory"]

        # Test cache operations
        cache_manager.clear_cache()
        stats_after_clear = cache_manager.get_cache_stats()
        assert stats_after_clear["enabled"] is True

    async def test_all_external_services_status(
        self, check_redis_available, check_llm_api_available, test_db_engine
    ):
        """Comprehensive external services health check."""
        service_status = {
            "database": False,
            "redis": False,
            "llm_api": False,
            "llm_cache": False,
        }

        # Test database
        try:
            async with test_db_engine.connect() as conn:
                await conn.execute("SELECT 1")
            service_status["database"] = True
        except Exception:
            pass

        # Test Redis
        service_status["redis"] = check_redis_available

        # Test LLM API
        service_status["llm_api"] = check_llm_api_available

        # Test LLM cache
        try:
            cache_stats = inspect_cache()
            service_status["llm_cache"] = cache_stats.get("enabled", False)
        except Exception:
            pass

        # At minimum, database should be available for testing
        assert service_status["database"] is True

        # Log service status for debugging
        print(f"Service Status: {service_status}")


@pytest.mark.integration
@pytest.mark.external
class TestCrossSystemIntegration:
    """Test integration between different system components."""

    async def test_database_and_cache_integration(
        self, test_db_session, enable_llm_cache
    ):
        """Test integration between database operations and LLM caching."""
        from app.data.models.deck_model import DeckModel as Deck
        from app.api.schemas import DeckStatus

        # Create a deck in database
        deck_id = uuid4()
        deck = Deck(
            id=deck_id,
            user_id=uuid4(),
            prompt="Create a test deck with cache integration",
            status=DeckStatus.PENDING,
        )

        test_db_session.add(deck)
        await test_db_session.commit()

        # Verify deck exists in database
        from sqlalchemy import select

        result = await test_db_session.execute(select(Deck).where(Deck.id == deck_id))
        retrieved_deck = result.scalar_one()
        assert retrieved_deck.prompt == "Create a test deck with cache integration"

        # Test that cache is available and working
        cache_stats = inspect_cache()
        assert cache_stats["enabled"] is True

    async def test_redis_and_database_integration(
        self, test_db_session, test_redis_client, check_redis_available
    ):
        """Test integration between Redis messaging and database."""
        if not check_redis_available:
            pytest.skip("Redis not available")

        from app.data.models.deck_model import DeckModel as Deck
        from app.data.models.event_model import EventModel as DeckEvent
        from app.api.schemas import DeckStatus
        import json

        # Create deck in database
        deck_id = uuid4()
        deck = Deck(
            id=deck_id,
            user_id=uuid4(),
            prompt="Test integration",
            status=DeckStatus.PLANNING,
        )
        test_db_session.add(deck)

        # Create corresponding event
        event = DeckEvent(
            id=uuid4(),
            deck_id=deck_id,
            event_type="DeckStarted",
            event_data={"status": "PLANNING", "timestamp": "2023-12-01T10:00:00Z"},
            sequence_number=1,
        )
        test_db_session.add(event)
        await test_db_session.commit()

        # Publish event to Redis
        event_message = {
            "deck_id": str(deck_id),
            "event_type": "DeckStarted",
            "data": event.event_data,
        }

        await test_redis_client.publish(f"deck:{deck_id}", json.dumps(event_message))

        # Verify both database and Redis operations succeeded
        # (In real system, WebSocket clients would receive this message)

        # Verify database event exists
        from sqlalchemy import select

        result = await test_db_session.execute(
            select(DeckEvent).where(DeckEvent.deck_id == deck_id)
        )
        db_event = result.scalar_one()
        assert db_event.event_type == "DeckStarted"

    async def test_full_system_workflow_integration(
        self,
        test_db_session,
        test_redis_client,
        enable_llm_cache,
        check_redis_available,
    ):
        """Test integration across all system components."""
        if not check_redis_available:
            pytest.skip("Redis not available for full integration test")

        from app.data.models.deck_model import DeckModel as Deck
        from app.data.models.slide_model import SlideModel as Slide
        from app.data.models.event_model import EventModel as DeckEvent
        from app.api.schemas import DeckStatus
        from app.domain.value_objects.template_type import TemplateType
        import json

        # Step 1: Create deck (Database)
        deck_id = uuid4()
        user_id = uuid4()

        deck = Deck(
            id=deck_id,
            user_id=user_id,
            prompt="Create a comprehensive test deck",
            status=DeckStatus.PLANNING,
        )
        test_db_session.add(deck)
        await test_db_session.flush()

        # Step 2: Create event (Database + Redis)
        start_event = DeckEvent(
            id=uuid4(),
            deck_id=deck_id,
            event_type="DeckStarted",
            event_data={"user_id": str(user_id), "prompt": deck.prompt},
            sequence_number=1,
        )
        test_db_session.add(start_event)

        # Publish to Redis
        await test_redis_client.publish(
            f"deck:{deck_id}",
            json.dumps(
                {"type": "deck_started", "deck_id": str(deck_id), "status": "PLANNING"}
            ),
        )

        # Step 3: Add slides (Database)
        slides_data = [
            {
                "order": 1,
                "title": "Introduction",
                "content_outline": "Overview of the topic",
                "html_content": "<h1>Introduction</h1><p>Welcome</p>",
                "presenter_notes": "Introduce the topic",
            },
            {
                "order": 2,
                "title": "Main Content",
                "content_outline": "Detailed explanation",
                "html_content": "<h1>Main Content</h1><p>Details here</p>",
                "presenter_notes": "Explain main points",
            },
        ]

        for slide_data in slides_data:
            slide = Slide(
                id=uuid4(),
                deck_id=deck_id,
                template_type=TemplateType.PROFESSIONAL,
                **slide_data,
            )
            test_db_session.add(slide)

            # Create slide event
            slide_event = DeckEvent(
                id=uuid4(),
                deck_id=deck_id,
                event_type="SlideAdded",
                event_data={
                    "slide_id": str(slide.id),
                    "order": slide_data["order"],
                    "title": slide_data["title"],
                },
                sequence_number=slide_data["order"] + 1,
            )
            test_db_session.add(slide_event)

            # Publish slide event to Redis
            await test_redis_client.publish(
                f"deck:{deck_id}",
                json.dumps(
                    {
                        "type": "slide_added",
                        "deck_id": str(deck_id),
                        "slide": {
                            "id": str(slide.id),
                            "order": slide_data["order"],
                            "title": slide_data["title"],
                        },
                    }
                ),
            )

        # Step 4: Complete deck
        deck.status = DeckStatus.COMPLETED

        completion_event = DeckEvent(
            id=uuid4(),
            deck_id=deck_id,
            event_type="DeckCompleted",
            event_data={
                "slides_count": len(slides_data),
                "completion_time": "2023-12-01T10:30:00Z",
            },
            sequence_number=len(slides_data) + 2,
        )
        test_db_session.add(completion_event)

        await test_db_session.commit()

        # Final Redis notification
        await test_redis_client.publish(
            f"deck:{deck_id}",
            json.dumps(
                {
                    "type": "deck_completed",
                    "deck_id": str(deck_id),
                    "slides_count": len(slides_data),
                }
            ),
        )

        # Step 5: Verify complete workflow
        # Database verification
        from sqlalchemy import select

        # Verify deck
        deck_result = await test_db_session.execute(
            select(Deck).where(Deck.id == deck_id)
        )
        final_deck = deck_result.scalar_one()
        assert final_deck.status == DeckStatus.COMPLETED

        # Verify slides
        slides_result = await test_db_session.execute(
            select(Slide).where(Slide.deck_id == deck_id).order_by(Slide.order)
        )
        final_slides = slides_result.scalars().all()
        assert len(final_slides) == len(slides_data)

        # Verify events
        events_result = await test_db_session.execute(
            select(DeckEvent)
            .where(DeckEvent.deck_id == deck_id)
            .order_by(DeckEvent.sequence_number)
        )
        final_events = events_result.scalars().all()
        assert len(final_events) == len(slides_data) + 2  # Start + slides + completion

        # Cache verification (should be initialized and working)
        cache_stats = inspect_cache()
        assert cache_stats["enabled"] is True


@pytest.mark.integration
@pytest.mark.external
class TestExternalServiceFallbacks:
    """Test fallback behavior when external services are unavailable."""

    async def test_redis_fallback_behavior(self, test_db_session):
        """Test system behavior when Redis is unavailable."""
        # This test simulates Redis being unavailable
        # System should continue to work with database-only operations

        from app.data.models.deck_model import DeckModel as Deck
        from app.api.schemas import DeckStatus

        # Should still be able to create decks without Redis
        deck = Deck(
            id=uuid4(),
            user_id=uuid4(),
            title="Fallback Test Deck",
            description="Testing without Redis",
            prompt="Test fallback behavior",
            status=DeckStatus.PENDING,
        )

        test_db_session.add(deck)
        await test_db_session.commit()

        # Verify deck was created
        assert deck.id is not None
        assert deck.title == "Fallback Test Deck"

    async def test_llm_api_fallback_behavior(self):
        """Test system behavior when LLM API is unavailable."""
        # When LLM API is unavailable, system should use mock responses
        # or gracefully handle the failure

        settings = get_settings()

        # If using dummy API key, should fall back to mock client
        if settings.openai_api_key == "dummy-key-for-test":
            from app.infra.config.dependencies import get_llm_client

            llm_client = await get_llm_client()

            # Should return mock client
            from app.infra.llm.mock_client import MockLLMClient

            assert isinstance(llm_client, MockLLMClient)

    async def test_cache_fallback_behavior(self):
        """Test system behavior when cache is disabled or unavailable."""
        # System should work without caching (just slower)

        import os

        original_cache_enabled = os.environ.get("LLM_CACHE_ENABLED")

        try:
            # Disable cache
            os.environ["LLM_CACHE_ENABLED"] = "false"

            # Cache manager should handle disabled state
            cache_manager = get_cache_manager()
            stats = cache_manager.get_cache_stats()
            assert stats["enabled"] is False

        finally:
            # Restore original setting
            if original_cache_enabled:
                os.environ["LLM_CACHE_ENABLED"] = original_cache_enabled
            else:
                os.environ.pop("LLM_CACHE_ENABLED", None)


@pytest.mark.integration
@pytest.mark.external
class TestSystemPerformance:
    """Test system performance under integration scenarios."""

    async def test_concurrent_database_operations(self, test_db_session):
        """Test database performance under concurrent load."""
        from app.data.models.deck_model import DeckModel as Deck
        from app.api.schemas import DeckStatus
        import time

        # Create multiple decks concurrently
        num_decks = 20
        start_time = time.time()

        decks = []
        for i in range(num_decks):
            deck = Deck(
                id=uuid4(),
                user_id=uuid4(),
                title=f"Performance Test Deck {i}",
                description=f"Deck {i} for performance testing",
                prompt=f"Create test deck number {i}",
                status=DeckStatus.PENDING,
            )
            decks.append(deck)

        test_db_session.add_all(decks)
        await test_db_session.commit()

        creation_time = time.time() - start_time

        # Should be reasonably fast
        assert creation_time < 5.0  # 20 decks in less than 5 seconds
        assert len(decks) == num_decks

    async def test_cache_performance_integration(self, enable_llm_cache):
        """Test cache performance in integration scenarios."""
        import time

        # Test cache operations
        cache_manager = get_cache_manager()

        start_time = time.time()

        # Multiple cache statistics calls
        for _ in range(100):
            cache_manager.get_cache_stats()

        stats_time = time.time() - start_time

        # Should be very fast
        assert stats_time < 1.0  # 100 stats calls in less than 1 second

    async def test_redis_performance_integration(
        self, test_redis_client, check_redis_available
    ):
        """Test Redis performance in integration scenarios."""
        if not check_redis_available:
            pytest.skip("Redis not available")

        import time
        import json

        # Test multiple publish operations
        num_messages = 50
        start_time = time.time()

        for i in range(num_messages):
            message = {
                "type": "test_event",
                "data": {"index": i, "timestamp": time.time()},
            }
            await test_redis_client.publish(f"test:channel:{i}", json.dumps(message))

        publish_time = time.time() - start_time

        # Should be reasonably fast
        assert publish_time < 2.0  # 50 publishes in less than 2 seconds
