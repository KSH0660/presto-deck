"""Integration tests for Redis messaging infrastructure."""

import os
import asyncio
import json
import pytest
import redis.asyncio as redis
from datetime import datetime, UTC
from uuid import uuid4

from app.api.schemas import Event
from app.core.config import settings
from app.infrastructure.messaging.redis_client import (
    RedisClient,
    RedisStreamPublisher,
    RedisStreamConsumer,
    RedisPubSubManager,
    RedisCacheManager,
)


# Attempt to ping Redis; skip tests only if ping fails
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


async def _ping_redis(url: str) -> bool:
    try:
        client = redis.Redis.from_url(url)
        await client.ping()
        aclose = getattr(client, "aclose", None)
        if callable(aclose):
            await aclose()
        else:
            close = getattr(client, "close", None)
            if asyncio.iscoroutinefunction(close):
                await close()
            elif callable(close):
                close()
        return True
    except Exception:
        return False


try:
    _can_connect = asyncio.run(_ping_redis(REDIS_URL))
except RuntimeError:
    loop = asyncio.new_event_loop()
    try:
        _can_connect = loop.run_until_complete(_ping_redis(REDIS_URL))
    finally:
        loop.close()

pytestmark = pytest.mark.skipif(
    not _can_connect, reason="Requires live Redis; ping failed"
)


class TestRedisClientIntegration:
    """Integration tests for RedisClient with real Redis instance."""

    @pytest.mark.asyncio
    async def test_redis_connection_lifecycle(self, mock_redis_client):
        """Test Redis connection initialization and cleanup."""
        redis_client = RedisClient(settings.redis_url)

        # Test initialization
        await redis_client.initialize()

        # Test health check
        health_status = await redis_client.health_check()
        assert health_status is True

        # Test get client
        client = redis_client.get_client()
        assert client is not None

        # Test basic Redis operation
        await client.set("test_key", "test_value")
        value = await client.get("test_key")
        assert value == "test_value"

        # Test cleanup
        await redis_client.close()

        # Health check should fail after close
        health_status = await redis_client.health_check()
        assert health_status is False

    @pytest.mark.asyncio
    async def test_redis_connection_pool_reuse(self, mock_redis_client):
        """Test Redis connection pool reuse across operations."""
        redis_client = RedisClient(settings.redis_url)
        await redis_client.initialize()

        try:
            client1 = redis_client.get_client()
            client2 = redis_client.get_client()

            # Should be the same client instance (from pool)
            assert client1 is client2

            # Test concurrent operations
            tasks = []
            for i in range(10):
                tasks.append(client1.set(f"concurrent_key_{i}", f"value_{i}"))

            await asyncio.gather(*tasks)

            # Verify all keys were set
            for i in range(10):
                value = await client1.get(f"concurrent_key_{i}")
                assert value == f"value_{i}"

        finally:
            await redis_client.close()


class TestRedisStreamIntegration:
    """Integration tests for Redis Streams functionality."""

    @pytest.fixture
    async def redis_client(self):
        """Create and initialize Redis client."""
        client = RedisClient(settings.redis_url)
        await client.initialize()

        # Clean up the stream before test
        try:
            redis_instance = client.get_client()
            await redis_instance.delete(settings.redis_stream_key)
        except Exception:
            pass  # Stream might not exist yet

        yield client

        # Clean up after test
        try:
            redis_instance = client.get_client()
            await redis_instance.delete(settings.redis_stream_key)
        except Exception:
            pass

        await client.close()

    @pytest.fixture
    async def stream_publisher(self, redis_client):
        """Create Redis stream publisher."""
        return RedisStreamPublisher(redis_client)

    @pytest.fixture
    async def stream_consumer(self, redis_client):
        """Create Redis stream consumer."""
        return RedisStreamConsumer(redis_client, "test-group", "test-consumer")

    @pytest.fixture
    def sample_event(self):
        """Create sample event for testing."""
        return Event(
            event_type="DeckStarted",
            deck_id=uuid4(),
            version=1,
            timestamp=datetime.now(UTC),
            payload={"test": "data", "number": 42},
        )

    @pytest.mark.asyncio
    async def test_stream_publish_and_consume(
        self, stream_publisher, stream_consumer, sample_event
    ):
        """Test publishing and consuming events through Redis Streams."""
        consumed_events = []

        async def event_handler(event):
            consumed_events.append(event)

        # Start consumer in background
        consumer_task = asyncio.create_task(
            self._consume_with_timeout(stream_consumer, event_handler, timeout=5.0)
        )

        # Give consumer time to start
        await asyncio.sleep(0.1)

        # Publish event
        stream_id = await stream_publisher.publish_event(sample_event)
        assert stream_id is not None
        assert isinstance(stream_id, str)

        # Wait for consumer to process
        await asyncio.sleep(0.5)

        # Stop consumer
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass

        # Verify event was consumed
        assert len(consumed_events) == 1
        consumed_event = consumed_events[0]

        assert consumed_event.event_type == sample_event.event_type
        assert consumed_event.deck_id == sample_event.deck_id
        assert consumed_event.version == sample_event.version
        assert consumed_event.payload == sample_event.payload

    @pytest.mark.asyncio
    async def test_multiple_events_ordering(self, stream_publisher, stream_consumer):
        """Test that multiple events maintain order in streams."""
        events = []
        valid_events = [
            "DeckStarted",
            "PlanUpdated",
            "SlideAdded",
            "SlideUpdated",
            "DeckCompleted",
        ]
        for i in range(5):
            event = Event(
                event_type=valid_events[i],
                deck_id=uuid4(),
                version=i + 1,
                timestamp=datetime.now(UTC),
                payload={"order": i},
            )
            events.append(event)

        consumed_events = []

        async def event_handler(event):
            consumed_events.append(event)

        # Start consumer
        consumer_task = asyncio.create_task(
            self._consume_with_timeout(stream_consumer, event_handler, timeout=5.0)
        )

        await asyncio.sleep(0.1)

        # Publish events in order
        for event in events:
            await stream_publisher.publish_event(event)
            await asyncio.sleep(0.01)  # Small delay to ensure ordering

        # Wait for processing
        await asyncio.sleep(1.0)

        # Stop consumer
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass

        # Verify all events consumed in order
        assert len(consumed_events) == 5
        for i, consumed_event in enumerate(consumed_events):
            assert consumed_event.event_type == valid_events[i]
            assert consumed_event.version == i + 1
            assert consumed_event.payload["order"] == i

    @pytest.mark.asyncio
    async def test_consumer_group_creation(self, stream_consumer, redis_client):
        """Test consumer group creation and idempotency."""
        # Create consumer group
        await stream_consumer.create_consumer_group()

        # Creating again should not fail (idempotent)
        await stream_consumer.create_consumer_group()

        # Verify group exists by checking Redis directly
        client = redis_client.get_client()
        groups = await client.xinfo_groups(settings.redis_stream_key)
        group_names = [group["name"] for group in groups]
        assert stream_consumer.consumer_group in group_names

    @pytest.mark.asyncio
    async def test_multiple_consumers_same_group(self, redis_client, sample_event):
        """Test multiple consumers in same group (load balancing)."""
        # Create two consumers in same group
        consumer1 = RedisStreamConsumer(redis_client, "load-balance-group", "consumer1")
        consumer2 = RedisStreamConsumer(redis_client, "load-balance-group", "consumer2")

        publisher = RedisStreamPublisher(redis_client)

        consumed_events_1 = []
        consumed_events_2 = []

        async def handler1(event):
            consumed_events_1.append(event)

        async def handler2(event):
            consumed_events_2.append(event)

        # Start both consumers
        task1 = asyncio.create_task(
            self._consume_with_timeout(consumer1, handler1, timeout=3.0)
        )
        task2 = asyncio.create_task(
            self._consume_with_timeout(consumer2, handler2, timeout=3.0)
        )

        await asyncio.sleep(0.2)

        # Publish multiple events
        events = []
        for i in range(6):
            event = Event(
                event_type=["DeckStarted", "PlanUpdated"][i % 2],
                deck_id=uuid4(),
                version=i + 1,
                timestamp=datetime.now(UTC),
                payload={"index": i},
            )
            events.append(event)
            await publisher.publish_event(event)
            await asyncio.sleep(0.05)

        # Wait for processing
        await asyncio.sleep(1.0)

        # Stop consumers
        task1.cancel()
        task2.cancel()
        try:
            await asyncio.gather(task1, task2, return_exceptions=True)
        except:
            pass

        # Verify events were distributed (load balanced)
        total_consumed = len(consumed_events_1) + len(consumed_events_2)
        assert total_consumed == 6

        # Each consumer should have processed some events
        assert len(consumed_events_1) > 0
        assert len(consumed_events_2) > 0

    async def _consume_with_timeout(self, consumer, handler, timeout=5.0):
        """Helper to consume events with timeout."""
        try:
            await asyncio.wait_for(
                consumer.consume_events(handler, batch_size=1, block_ms=100),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            pass


class TestRedisPubSubIntegration:
    """Integration tests for Redis Pub/Sub functionality."""

    @pytest.fixture
    async def redis_client(self):
        """Create and initialize Redis client."""
        client = RedisClient(settings.redis_url)
        await client.initialize()
        yield client
        await client.close()

    @pytest.fixture
    async def pubsub_manager(self, redis_client):
        """Create Redis Pub/Sub manager."""
        return RedisPubSubManager(redis_client)

    @pytest.fixture
    def sample_event(self):
        """Create sample event for testing."""
        return Event(
            event_type="SlideAdded",
            deck_id=uuid4(),
            version=1,
            timestamp=datetime.now(UTC),
            payload={"message": "test pubsub"},
        )

    @pytest.mark.asyncio
    async def test_pubsub_publish_subscribe(self, pubsub_manager, sample_event):
        """Test basic publish/subscribe functionality."""
        deck_id = sample_event.deck_id
        received_events = []

        # Start subscriber
        async def subscriber():
            async for event in pubsub_manager.subscribe_to_deck_channel(deck_id):
                received_events.append(event)
                break  # Exit after first event

        subscriber_task = asyncio.create_task(subscriber())

        # Give subscriber time to connect
        await asyncio.sleep(0.2)

        # Publish event
        await pubsub_manager.publish_to_deck_channel(deck_id, sample_event)

        # Wait for processing
        await asyncio.sleep(0.5)

        # Stop subscriber
        subscriber_task.cancel()
        try:
            await subscriber_task
        except asyncio.CancelledError:
            pass

        # Verify event was received
        assert len(received_events) == 1
        received_event = received_events[0]

        assert received_event.event_type == sample_event.event_type
        assert received_event.deck_id == sample_event.deck_id
        assert received_event.version == sample_event.version
        assert received_event.payload == sample_event.payload

    @pytest.mark.asyncio
    async def test_multiple_subscribers_broadcast(self, pubsub_manager):
        """Test broadcasting to multiple subscribers."""
        deck_id = uuid4()
        event = Event(
            event_type="SlideUpdated",
            deck_id=deck_id,
            version=1,
            timestamp=datetime.now(UTC),
            payload={"broadcast": True},
        )

        received_events_1 = []
        received_events_2 = []

        # Start two subscribers
        async def subscriber1():
            async for evt in pubsub_manager.subscribe_to_deck_channel(deck_id):
                received_events_1.append(evt)
                break

        async def subscriber2():
            async for evt in pubsub_manager.subscribe_to_deck_channel(deck_id):
                received_events_2.append(evt)
                break

        sub1_task = asyncio.create_task(subscriber1())
        sub2_task = asyncio.create_task(subscriber2())

        # Give subscribers time to connect
        await asyncio.sleep(0.3)

        # Publish event
        await pubsub_manager.publish_to_deck_channel(deck_id, event)

        # Wait for processing
        await asyncio.sleep(0.5)

        # Stop subscribers
        for task in [sub1_task, sub2_task]:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Both subscribers should have received the event
        assert len(received_events_1) == 1
        assert len(received_events_2) == 1

        assert received_events_1[0].event_type == "SlideUpdated"
        assert received_events_2[0].event_type == "SlideUpdated"

    @pytest.mark.asyncio
    async def test_channel_isolation(self, pubsub_manager):
        """Test that different deck channels are isolated."""
        deck1_id = uuid4()
        deck2_id = uuid4()

        event1 = Event(
            event_type="DeckStarted",
            deck_id=deck1_id,
            version=1,
            timestamp=datetime.now(UTC),
            payload={"deck": "deck1"},
        )

        event2 = Event(
            event_type="PlanUpdated",
            deck_id=deck2_id,
            version=1,
            timestamp=datetime.now(UTC),
            payload={"deck": "deck2"},
        )

        received_deck1 = []
        received_deck2 = []

        # Start subscribers for different decks
        async def subscriber1():
            async for evt in pubsub_manager.subscribe_to_deck_channel(deck1_id):
                received_deck1.append(evt)
                if len(received_deck1) >= 1:
                    break

        async def subscriber2():
            async for evt in pubsub_manager.subscribe_to_deck_channel(deck2_id):
                received_deck2.append(evt)
                if len(received_deck2) >= 1:
                    break

        sub1_task = asyncio.create_task(subscriber1())
        sub2_task = asyncio.create_task(subscriber2())

        await asyncio.sleep(0.3)

        # Publish to both channels
        await pubsub_manager.publish_to_deck_channel(deck1_id, event1)
        await pubsub_manager.publish_to_deck_channel(deck2_id, event2)

        await asyncio.sleep(0.5)

        # Stop subscribers
        for task in [sub1_task, sub2_task]:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Each subscriber should only receive events from their deck
        assert len(received_deck1) == 1
        assert len(received_deck2) == 1

        assert received_deck1[0].event_type == "DeckStarted"
        assert received_deck1[0].payload["deck"] == "deck1"

        assert received_deck2[0].event_type == "PlanUpdated"
        assert received_deck2[0].payload["deck"] == "deck2"


class TestRedisCacheIntegration:
    """Integration tests for Redis cache functionality."""

    @pytest.fixture
    async def redis_client(self):
        """Create and initialize Redis client."""
        client = RedisClient(settings.redis_url)
        await client.initialize()
        yield client

        # Cleanup test keys
        redis_instance = client.get_client()
        test_keys = await redis_instance.keys("cancel:deck:*")
        test_keys.extend(await redis_instance.keys("test:*"))
        if test_keys:
            await redis_instance.delete(*test_keys)

        await client.close()

    @pytest.fixture
    async def cache_manager(self, redis_client):
        """Create Redis cache manager."""
        return RedisCacheManager(redis_client)

    @pytest.mark.asyncio
    async def test_cancellation_flag_operations(self, cache_manager):
        """Test cancellation flag set/check/clear operations."""
        deck_id = uuid4()

        # Initially should not be cancelled
        is_cancelled = await cache_manager.check_cancellation_flag(deck_id)
        assert is_cancelled is False

        # Set cancellation flag
        await cache_manager.set_cancellation_flag(deck_id, ttl=60)

        # Should now be cancelled
        is_cancelled = await cache_manager.check_cancellation_flag(deck_id)
        assert is_cancelled is True

        # Clear cancellation flag
        await cache_manager.clear_cancellation_flag(deck_id)

        # Should no longer be cancelled
        is_cancelled = await cache_manager.check_cancellation_flag(deck_id)
        assert is_cancelled is False

    @pytest.mark.asyncio
    async def test_cancellation_flag_ttl(self, cache_manager, redis_client):
        """Test cancellation flag TTL expiration."""
        deck_id = uuid4()

        # Set flag with very short TTL
        await cache_manager.set_cancellation_flag(deck_id, ttl=1)

        # Should be set initially
        is_cancelled = await cache_manager.check_cancellation_flag(deck_id)
        assert is_cancelled is True

        # Wait for expiration
        await asyncio.sleep(1.5)

        # Should be expired
        is_cancelled = await cache_manager.check_cancellation_flag(deck_id)
        assert is_cancelled is False

    @pytest.mark.asyncio
    async def test_temporary_data_operations(self, cache_manager):
        """Test temporary data set/get operations."""
        test_key = "test:temp_data"
        test_data = {
            "status": "processing",
            "progress": 75,
            "metadata": {"user": "test", "started": "2024-01-01T10:00:00"},
        }

        # Initially should not exist
        retrieved_data = await cache_manager.get_temporary_data(test_key)
        assert retrieved_data is None

        # Set temporary data
        await cache_manager.set_temporary_data(test_key, test_data, ttl=60)

        # Should now exist and match
        retrieved_data = await cache_manager.get_temporary_data(test_key)
        assert retrieved_data == test_data
        assert retrieved_data["status"] == "processing"
        assert retrieved_data["progress"] == 75
        assert retrieved_data["metadata"]["user"] == "test"

    @pytest.mark.asyncio
    async def test_temporary_data_ttl(self, cache_manager):
        """Test temporary data TTL expiration."""
        test_key = "test:ttl_data"
        test_data = {"expiring": True}

        # Set data with short TTL
        await cache_manager.set_temporary_data(test_key, test_data, ttl=1)

        # Should exist initially
        retrieved_data = await cache_manager.get_temporary_data(test_key)
        assert retrieved_data == test_data

        # Wait for expiration
        await asyncio.sleep(1.5)

        # Should be expired
        retrieved_data = await cache_manager.get_temporary_data(test_key)
        assert retrieved_data is None

    @pytest.mark.asyncio
    async def test_multiple_deck_cancellation_isolation(self, cache_manager):
        """Test that cancellation flags are isolated between decks."""
        deck1_id = uuid4()
        deck2_id = uuid4()

        # Set cancellation for deck1 only
        await cache_manager.set_cancellation_flag(deck1_id)

        # Check both decks
        deck1_cancelled = await cache_manager.check_cancellation_flag(deck1_id)
        deck2_cancelled = await cache_manager.check_cancellation_flag(deck2_id)

        assert deck1_cancelled is True
        assert deck2_cancelled is False

        # Clear deck1 cancellation
        await cache_manager.clear_cancellation_flag(deck1_id)

        # Verify only deck1 is affected
        deck1_cancelled = await cache_manager.check_cancellation_flag(deck1_id)
        deck2_cancelled = await cache_manager.check_cancellation_flag(deck2_id)

        assert deck1_cancelled is False
        assert deck2_cancelled is False

    @pytest.mark.asyncio
    async def test_cache_operations_with_special_characters(self, cache_manager):
        """Test cache operations with special characters in data."""
        test_key = "test:special_chars"
        test_data = {
            "unicode": "测试数据 🔥",
            "json_chars": '{"nested": "value", "array": [1, 2, 3]}',
            "special_symbols": "!@#$%^&*()_+-={}[]|\\:;\"'<>?,./",
        }

        # Set and retrieve data with special characters
        await cache_manager.set_temporary_data(test_key, test_data)

        retrieved_data = await cache_manager.get_temporary_data(test_key)
        assert retrieved_data == test_data
        assert retrieved_data["unicode"] == "测试数据 🔥"
        assert retrieved_data["json_chars"] == '{"nested": "value", "array": [1, 2, 3]}'
        assert retrieved_data["special_symbols"] == "!@#$%^&*()_+-={}[]|\\:;\"'<>?,./"

    @pytest.mark.asyncio
    async def test_concurrent_cache_operations(self, cache_manager):
        """Test concurrent cache operations."""
        deck_ids = [uuid4() for _ in range(10)]

        # Concurrent set operations
        set_tasks = []
        for i, deck_id in enumerate(deck_ids):
            task = cache_manager.set_cancellation_flag(deck_id, ttl=60)
            set_tasks.append(task)

        await asyncio.gather(*set_tasks)

        # Concurrent check operations
        check_tasks = []
        for deck_id in deck_ids:
            task = cache_manager.check_cancellation_flag(deck_id)
            check_tasks.append(task)

        results = await asyncio.gather(*check_tasks)

        # All should be True
        assert all(results)

        # Concurrent clear operations
        clear_tasks = []
        for deck_id in deck_ids:
            task = cache_manager.clear_cancellation_flag(deck_id)
            clear_tasks.append(task)

        await asyncio.gather(*clear_tasks)

        # Verify all cleared
        final_check_tasks = []
        for deck_id in deck_ids:
            task = cache_manager.check_cancellation_flag(deck_id)
            final_check_tasks.append(task)

        final_results = await asyncio.gather(*final_check_tasks)

        # All should be False
        assert not any(final_results)
