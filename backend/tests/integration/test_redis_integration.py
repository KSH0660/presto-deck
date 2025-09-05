"""
Integration tests for Redis messaging and caching functionality.

These tests verify actual Redis communication for ARQ queues, WebSocket broadcasting,
and LLM cache operations.
"""

import pytest
import asyncio
import json
from uuid import uuid4

from app.infra.messaging.arq_client import ARQClient, get_arq_client
from app.infra.messaging.websocket_broadcaster import WebSocketBroadcaster
from app.infra.messaging.redis_client import get_redis_client
from app.infra.llm.cache_manager import get_cache_manager


@pytest.mark.integration
@pytest.mark.external
class TestRedisConnection:
    """Test basic Redis connectivity and operations."""

    async def test_redis_connection(self, test_redis_client):
        """Test that Redis connection works."""
        # Basic ping test
        pong = await test_redis_client.ping()
        assert pong is True

    async def test_redis_basic_operations(self, test_redis_client):
        """Test basic Redis set/get operations."""
        test_key = "test:integration"
        test_value = "integration_test_value"

        # Set value
        await test_redis_client.set(test_key, test_value)

        # Get value
        retrieved_value = await test_redis_client.get(test_key)
        assert retrieved_value.decode("utf-8") == test_value

        # Delete value
        await test_redis_client.delete(test_key)

        # Verify deletion
        deleted_value = await test_redis_client.get(test_key)
        assert deleted_value is None

    async def test_redis_json_operations(self, test_redis_client):
        """Test Redis operations with JSON data."""
        test_key = "test:json:integration"
        test_data = {
            "deck_id": str(uuid4()),
            "status": "GENERATING",
            "timestamp": "2023-12-01T10:00:00Z",
            "metadata": {"slides_count": 5, "user_id": str(uuid4())},
        }

        # Store JSON data
        json_str = json.dumps(test_data)
        await test_redis_client.set(test_key, json_str)

        # Retrieve and parse JSON
        retrieved_str = await test_redis_client.get(test_key)
        retrieved_data = json.loads(retrieved_str.decode("utf-8"))

        assert retrieved_data["deck_id"] == test_data["deck_id"]
        assert retrieved_data["status"] == test_data["status"]
        assert (
            retrieved_data["metadata"]["slides_count"]
            == test_data["metadata"]["slides_count"]
        )

    async def test_redis_expiration(self, test_redis_client):
        """Test Redis key expiration functionality."""
        test_key = "test:expiration"
        test_value = "expires_soon"

        # Set with short TTL
        await test_redis_client.setex(test_key, 2, test_value)  # 2 seconds

        # Should exist immediately
        value = await test_redis_client.get(test_key)
        assert value.decode("utf-8") == test_value

        # Wait for expiration
        await asyncio.sleep(3)

        # Should be expired
        expired_value = await test_redis_client.get(test_key)
        assert expired_value is None


@pytest.mark.integration
@pytest.mark.external
class TestRedisMessaging:
    """Test Redis-based messaging functionality."""

    async def test_redis_pub_sub(self, test_redis_client):
        """Test Redis pub/sub functionality."""
        channel = "test:channel"
        test_message = {"event": "test", "data": {"key": "value"}}

        # Subscribe to channel
        pubsub = test_redis_client.pubsub()
        await pubsub.subscribe(channel)

        # Publish message
        await test_redis_client.publish(channel, json.dumps(test_message))

        # Receive message
        message = await pubsub.get_message(timeout=5.0)
        if message and message["type"] == "message":
            received_data = json.loads(message["data"].decode("utf-8"))
            assert received_data["event"] == test_message["event"]
            assert received_data["data"]["key"] == test_message["data"]["key"]

        await pubsub.unsubscribe(channel)
        await pubsub.close()

    async def test_redis_streams(self, test_redis_client):
        """Test Redis streams functionality."""
        stream_key = "test:events"
        test_events = [
            {"event_type": "DeckStarted", "deck_id": str(uuid4())},
            {"event_type": "SlideAdded", "slide_id": str(uuid4())},
            {"event_type": "DeckCompleted", "slides_count": 5},
        ]

        # Add events to stream
        for event in test_events:
            await test_redis_client.xadd(stream_key, event)

        # Read events from stream
        events = await test_redis_client.xread({stream_key: 0}, count=10)

        assert len(events) == 1  # One stream
        stream_name, messages = events[0]
        assert stream_name.decode("utf-8") == stream_key
        assert len(messages) == len(test_events)

        # Verify event data
        for i, (msg_id, fields) in enumerate(messages):
            # Decode fields
            decoded_fields = {
                k.decode("utf-8"): v.decode("utf-8") for k, v in fields.items()
            }
            assert decoded_fields["event_type"] == test_events[i]["event_type"]

    async def test_redis_list_operations(self, test_redis_client):
        """Test Redis list operations for queues."""
        queue_key = "test:queue"
        test_jobs = [
            {"job_id": str(uuid4()), "type": "generate_slide"},
            {"job_id": str(uuid4()), "type": "process_deck"},
            {"job_id": str(uuid4()), "type": "send_notification"},
        ]

        # Push jobs to queue
        for job in test_jobs:
            await test_redis_client.lpush(queue_key, json.dumps(job))

        # Pop jobs from queue (FIFO)
        processed_jobs = []
        while await test_redis_client.llen(queue_key) > 0:
            job_data = await test_redis_client.rpop(queue_key)
            if job_data:
                processed_jobs.append(json.loads(job_data.decode("utf-8")))

        assert len(processed_jobs) == len(test_jobs)
        # Jobs should be processed in reverse order (LIFO due to lpush/rpop)
        for i, job in enumerate(reversed(test_jobs)):
            assert processed_jobs[i]["job_id"] == job["job_id"]


@pytest.mark.integration
@pytest.mark.external
class TestARQIntegration:
    """Test ARQ job queue integration with Redis."""

    @pytest.fixture
    async def arq_client(self, check_redis_available):
        """Create ARQ client for testing."""
        if not check_redis_available:
            pytest.skip("Redis not available for ARQ testing")

        client = await get_arq_client()
        yield client
        # Cleanup would happen in ARQ client teardown

    async def test_arq_job_enqueue(self, arq_client: ARQClient):
        """Test enqueueing jobs with ARQ."""
        job_data = {
            "deck_id": str(uuid4()),
            "user_id": str(uuid4()),
            "prompt": "Test deck generation",
        }

        # Enqueue a job
        job_id = await arq_client.enqueue_job("generate_deck", **job_data)
        assert job_id is not None

        # Job ID should be a string
        assert isinstance(job_id, str)

    async def test_arq_job_with_delay(self, arq_client: ARQClient):
        """Test enqueueing delayed jobs."""
        import time

        job_data = {"slide_id": str(uuid4()), "content": "Test slide content"}

        # Enqueue job with delay
        future_time = time.time() + 5  # 5 seconds in future
        job_id = await arq_client.enqueue_job(
            "process_slide", defer_until=future_time, **job_data
        )

        assert job_id is not None

    async def test_arq_job_priority(self, arq_client: ARQClient):
        """Test job priority handling."""
        high_priority_job = {"deck_id": str(uuid4()), "priority": "high"}

        low_priority_job = {"deck_id": str(uuid4()), "priority": "low"}

        # Enqueue jobs with different priorities
        high_job_id = await arq_client.enqueue_job(
            "urgent_task",
            job_priority=10,  # Higher number = higher priority
            **high_priority_job,
        )

        low_job_id = await arq_client.enqueue_job(
            "background_task", job_priority=1, **low_priority_job
        )

        assert high_job_id is not None
        assert low_job_id is not None
        assert high_job_id != low_job_id


@pytest.mark.integration
@pytest.mark.external
class TestWebSocketBroadcaster:
    """Test WebSocket broadcasting via Redis."""

    @pytest.fixture
    async def ws_broadcaster(self, check_redis_available):
        """Create WebSocket broadcaster for testing."""
        if not check_redis_available:
            pytest.skip("Redis not available for WebSocket testing")

        redis_client = await get_redis_client()
        broadcaster = WebSocketBroadcaster(redis_client=redis_client)
        yield broadcaster
        await redis_client.close()

    async def test_broadcast_message(
        self, ws_broadcaster: WebSocketBroadcaster, test_redis_client
    ):
        """Test broadcasting messages to WebSocket channels."""
        channel = f"deck:{uuid4()}"
        test_message = {
            "type": "slide_updated",
            "data": {"slide_id": str(uuid4()), "title": "Updated Slide Title"},
        }

        # Subscribe to channel to receive broadcast
        pubsub = test_redis_client.pubsub()
        await pubsub.subscribe(channel)

        # Broadcast message
        await ws_broadcaster.broadcast(channel, test_message)

        # Receive broadcast message
        message = await pubsub.get_message(timeout=5.0)
        if message and message["type"] == "message":
            received_data = json.loads(message["data"].decode("utf-8"))
            assert received_data["type"] == test_message["type"]
            assert received_data["data"]["slide_id"] == test_message["data"]["slide_id"]

        await pubsub.unsubscribe(channel)
        await pubsub.close()

    async def test_broadcast_to_multiple_channels(
        self, ws_broadcaster: WebSocketBroadcaster, test_redis_client
    ):
        """Test broadcasting to multiple channels."""
        deck_id = uuid4()
        channels = [f"deck:{deck_id}", f"user:{uuid4()}", "global:notifications"]

        test_message = {"type": "deck_completed", "data": {"deck_id": str(deck_id)}}

        # Subscribe to all channels
        pubsub = test_redis_client.pubsub()
        for channel in channels:
            await pubsub.subscribe(channel)

        # Broadcast to all channels
        for channel in channels:
            await ws_broadcaster.broadcast(channel, test_message)

        # Receive messages from all channels
        received_messages = 0
        while received_messages < len(channels):
            message = await pubsub.get_message(timeout=5.0)
            if message and message["type"] == "message":
                received_data = json.loads(message["data"].decode("utf-8"))
                assert received_data["type"] == test_message["type"]
                received_messages += 1

        await pubsub.unsubscribe(*channels)
        await pubsub.close()

    async def test_broadcast_heartbeat(self, ws_broadcaster: WebSocketBroadcaster):
        """Test broadcasting heartbeat messages."""
        channel = f"deck:{uuid4()}"

        # Broadcast heartbeat
        await ws_broadcaster.broadcast_heartbeat(channel)

        # Heartbeat should be broadcasted successfully
        # In a real scenario, WebSocket clients would receive this


@pytest.mark.integration
@pytest.mark.cache
@pytest.mark.external
class TestRedisLLMCache:
    """Test Redis-based LLM caching."""

    @pytest.fixture
    def redis_cache_settings(self):
        """Configure Redis cache for testing."""
        import os

        original_cache_type = os.environ.get("LLM_CACHE_TYPE")
        os.environ["LLM_CACHE_TYPE"] = "redis"

        yield

        # Restore original setting
        if original_cache_type:
            os.environ["LLM_CACHE_TYPE"] = original_cache_type
        else:
            os.environ.pop("LLM_CACHE_TYPE", None)

    async def test_redis_cache_initialization(
        self, redis_cache_settings, check_redis_available
    ):
        """Test Redis cache initialization."""
        if not check_redis_available:
            pytest.skip("Redis not available for cache testing")

        cache_manager = get_cache_manager()
        cache_manager.initialize_cache()

        stats = cache_manager.get_cache_stats()
        assert stats["enabled"] is True
        assert stats["type"] == "redis"

    async def test_redis_cache_operations(
        self, redis_cache_settings, check_redis_available, test_redis_client
    ):
        """Test Redis cache set/get operations."""
        if not check_redis_available:
            pytest.skip("Redis not available for cache testing")

        # Initialize Redis cache
        cache_manager = get_cache_manager()
        cache_manager.initialize_cache()

        # Manually add cache entry to Redis
        cache_key = "langchain:test:cache:key"
        cache_value = {
            "prompt": "Test prompt for caching",
            "response": "Test LLM response",
            "timestamp": "2023-12-01T10:00:00Z",
        }

        await test_redis_client.setex(
            cache_key, 3600, json.dumps(cache_value)  # 1 hour TTL
        )

        # Retrieve cache entry
        retrieved_value = await test_redis_client.get(cache_key)
        assert retrieved_value is not None

        retrieved_data = json.loads(retrieved_value.decode("utf-8"))
        assert retrieved_data["prompt"] == cache_value["prompt"]
        assert retrieved_data["response"] == cache_value["response"]

    async def test_redis_cache_cleanup(
        self, redis_cache_settings, check_redis_available, test_redis_client
    ):
        """Test Redis cache cleanup operations."""
        if not check_redis_available:
            pytest.skip("Redis not available for cache testing")

        # Add test cache entries
        cache_keys = [
            "langchain:test:entry:1",
            "langchain:test:entry:2",
            "langchain:test:entry:3",
        ]

        for key in cache_keys:
            await test_redis_client.set(key, json.dumps({"test": "data"}))

        # Verify entries exist
        for key in cache_keys:
            value = await test_redis_client.get(key)
            assert value is not None

        # Clear cache using manager
        cache_manager = get_cache_manager()
        cache_manager.clear_cache()

        # Verify entries are cleared
        remaining_keys = await test_redis_client.keys("langchain:*")
        assert len(remaining_keys) == 0


@pytest.mark.integration
@pytest.mark.external
class TestRedisPerformance:
    """Test Redis performance characteristics."""

    async def test_redis_throughput(self, test_redis_client):
        """Test Redis throughput for typical operations."""
        import time

        # Test set operations
        start_time = time.time()
        for i in range(100):
            await test_redis_client.set(f"perf:test:{i}", f"value_{i}")
        set_time = time.time() - start_time

        # Test get operations
        start_time = time.time()
        for i in range(100):
            await test_redis_client.get(f"perf:test:{i}")
        get_time = time.time() - start_time

        # Performance should be reasonable
        assert set_time < 1.0  # 100 sets in less than 1 second
        assert get_time < 0.5  # 100 gets in less than 0.5 seconds

    async def test_redis_pipeline_performance(self, test_redis_client):
        """Test Redis pipeline for batch operations."""
        import time

        # Test pipelined operations
        start_time = time.time()
        pipe = test_redis_client.pipeline()
        for i in range(100):
            pipe.set(f"pipe:test:{i}", f"value_{i}")
        await pipe.execute()
        pipeline_time = time.time() - start_time

        # Pipeline should be faster than individual operations
        assert pipeline_time < 0.5  # Should be very fast with pipelining

    async def test_redis_memory_usage(self, test_redis_client):
        """Test Redis memory usage for cache data."""
        # Get initial memory info
        initial_info = await test_redis_client.info("memory")
        initial_memory = initial_info.get("used_memory", 0)

        # Add cache data
        large_data = {"content": "x" * 10000}  # 10KB of data
        for i in range(50):
            await test_redis_client.set(f"memory:test:{i}", json.dumps(large_data))

        # Get final memory info
        final_info = await test_redis_client.info("memory")
        final_memory = final_info.get("used_memory", 0)

        # Memory should have increased
        memory_increase = final_memory - initial_memory
        assert memory_increase > 400000  # Should be roughly 50 * 10KB + overhead
