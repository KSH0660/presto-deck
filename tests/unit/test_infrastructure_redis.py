"""Unit tests for Redis infrastructure components."""

import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from redis.exceptions import RedisError, ResponseError

from app.api.schemas import Event
from app.core.config import settings
from app.domain.exceptions import MessagingException
from app.infrastructure.messaging.redis_client import (
    RedisClient,
    RedisStreamPublisher,
    RedisStreamConsumer,
    RedisPubSubManager,
    RedisCacheManager,
)


class TestRedisClient:
    """Test cases for RedisClient."""

    @pytest.fixture
    def redis_client(self):
        """Create Redis client instance."""
        return RedisClient("redis://localhost:6379/0")

    @pytest.mark.asyncio
    async def test_initialize_success(self, redis_client):
        """Test successful Redis initialization."""
        mock_pool = Mock()
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()

        with (
            patch("redis.asyncio.ConnectionPool.from_url", return_value=mock_pool),
            patch(
                "app.infrastructure.messaging.redis_client.Redis",
                return_value=mock_redis,
            ),
        ):

            await redis_client.initialize()

            assert redis_client.pool == mock_pool
            assert redis_client.redis_client == mock_redis
            mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_connection_failure(self, redis_client):
        """Test Redis initialization with connection failure."""
        with patch(
            "redis.asyncio.ConnectionPool.from_url",
            side_effect=RedisError("Connection failed"),
        ):

            with pytest.raises(MessagingException) as exc:
                await redis_client.initialize()

            assert "Redis initialization failed" in str(exc.value)

    @pytest.mark.asyncio
    async def test_close(self, redis_client):
        """Test closing Redis connection."""
        mock_redis = AsyncMock()
        redis_client.redis_client = mock_redis

        await redis_client.close()

        mock_redis.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_health_check_success(self, redis_client):
        """Test successful health check."""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        redis_client.redis_client = mock_redis

        result = await redis_client.health_check()

        assert result is True
        mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_no_client(self, redis_client):
        """Test health check with no client."""
        result = await redis_client.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_ping_failure(self, redis_client):
        """Test health check with ping failure."""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(side_effect=RedisError("Connection lost"))
        redis_client.redis_client = mock_redis

        result = await redis_client.health_check()

        assert result is False

    def test_get_client_success(self, redis_client):
        """Test getting Redis client successfully."""
        mock_redis = Mock()
        redis_client.redis_client = mock_redis

        result = redis_client.get_client()

        assert result == mock_redis

    def test_get_client_not_initialized(self, redis_client):
        """Test getting Redis client when not initialized."""
        with pytest.raises(MessagingException) as exc:
            redis_client.get_client()

        assert "Redis client not initialized" in str(exc.value)


class TestRedisStreamPublisher:
    """Test cases for RedisStreamPublisher."""

    @pytest.fixture
    def mock_redis_client(self):
        """Create mock Redis client."""
        client = Mock()
        mock_redis = AsyncMock()
        client.get_client.return_value = mock_redis
        return client, mock_redis

    @pytest.fixture
    def stream_publisher(self, mock_redis_client):
        """Create stream publisher with mock."""
        client, _ = mock_redis_client
        return RedisStreamPublisher(client)

    @pytest.fixture
    def sample_event(self):
        """Create sample event."""
        return Event(
            event_type="DeckStarted",
            deck_id=uuid4(),
            version=1,
            timestamp=datetime.now(),
            payload={"title": "Test Deck"},
        )

    @pytest.mark.asyncio
    async def test_publish_event_success(
        self, stream_publisher, mock_redis_client, sample_event
    ):
        """Test successful event publishing."""
        _, mock_redis = mock_redis_client
        mock_redis.xadd = AsyncMock(return_value="1234567890-0")

        with patch(
            "app.core.observability.metrics.record_redis_operation"
        ) as mock_metrics:
            stream_id = await stream_publisher.publish_event(sample_event)

        assert stream_id == "1234567890-0"
        mock_redis.xadd.assert_called_once()

        # Check xadd was called with correct data
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == settings.redis_stream_key
        event_data = call_args[0][1]

        assert event_data["event_type"] == "DeckStarted"
        assert event_data["deck_id"] == str(sample_event.deck_id)
        assert event_data["version"] == "1"
        assert json.loads(event_data["payload"]) == {"title": "Test Deck"}

        mock_metrics.assert_called_with("stream_publish", "success")

    @pytest.mark.asyncio
    async def test_publish_event_redis_error(
        self, stream_publisher, mock_redis_client, sample_event
    ):
        """Test event publishing with Redis error."""
        _, mock_redis = mock_redis_client
        mock_redis.xadd = AsyncMock(side_effect=RedisError("Stream error"))

        with patch(
            "app.core.observability.metrics.record_redis_operation"
        ) as mock_metrics:
            with pytest.raises(MessagingException) as exc:
                await stream_publisher.publish_event(sample_event)

        assert "Stream publish failed" in str(exc.value)
        mock_metrics.assert_called_with("stream_publish", "error")


class TestRedisStreamConsumer:
    """Test cases for RedisStreamConsumer."""

    @pytest.fixture
    def mock_redis_client(self):
        """Create mock Redis client."""
        client = Mock()
        mock_redis = AsyncMock()
        client.get_client.return_value = mock_redis
        return client, mock_redis

    @pytest.fixture
    def stream_consumer(self, mock_redis_client):
        """Create stream consumer with mock."""
        client, _ = mock_redis_client
        return RedisStreamConsumer(client, "test-group", "test-consumer")

    @pytest.mark.asyncio
    async def test_create_consumer_group_success(
        self, stream_consumer, mock_redis_client
    ):
        """Test successful consumer group creation."""
        _, mock_redis = mock_redis_client
        mock_redis.xgroup_create = AsyncMock()

        await stream_consumer.create_consumer_group()

        mock_redis.xgroup_create.assert_called_once_with(
            name=settings.redis_stream_key,
            groupname="test-group",
            id="0",
            mkstream=True,
        )

    @pytest.mark.asyncio
    async def test_create_consumer_group_already_exists(
        self, stream_consumer, mock_redis_client
    ):
        """Test consumer group creation when group already exists."""
        _, mock_redis = mock_redis_client
        mock_redis.xgroup_create = AsyncMock(
            side_effect=ResponseError("BUSYGROUP Consumer group already exists")
        )

        # Should not raise exception
        await stream_consumer.create_consumer_group()

    @pytest.mark.asyncio
    async def test_create_consumer_group_other_error(
        self, stream_consumer, mock_redis_client
    ):
        """Test consumer group creation with other error."""
        _, mock_redis = mock_redis_client
        mock_redis.xgroup_create = AsyncMock(side_effect=ResponseError("Other error"))

        with pytest.raises(MessagingException) as exc:
            await stream_consumer.create_consumer_group()

        assert "Failed to create consumer group" in str(exc.value)

    def test_parse_event(self, stream_consumer):
        """Test event parsing from Redis fields."""
        deck_id = uuid4()
        fields = {
            "event_type": "DeckStarted",
            "deck_id": str(deck_id),
            "version": "1",
            "timestamp": "2024-01-01T00:00:00",
            "payload": '{"title": "Test Deck"}',
        }

        event = stream_consumer._parse_event(fields)

        assert event.event_type == "DeckStarted"
        assert event.deck_id == deck_id
        assert event.version == 1
        assert event.timestamp.isoformat().startswith("2024-01-01T00:00:00")
        assert event.payload == {"title": "Test Deck"}

    def test_parse_event_no_payload(self, stream_consumer):
        """Test event parsing without payload."""
        deck_id = uuid4()
        fields = {
            "event_type": "DeckStarted",
            "deck_id": str(deck_id),
            "version": "1",
            "timestamp": "2024-01-01T00:00:00",
        }

        event = stream_consumer._parse_event(fields)

        assert event.payload == {}


class TestRedisPubSubManager:
    """Test cases for RedisPubSubManager."""

    @pytest.fixture
    def mock_redis_client(self):
        """Create mock Redis client."""
        client = Mock()
        mock_redis = AsyncMock()
        client.get_client.return_value = mock_redis
        return client, mock_redis

    @pytest.fixture
    def pubsub_manager(self, mock_redis_client):
        """Create pubsub manager with mock."""
        client, _ = mock_redis_client
        return RedisPubSubManager(client)

    @pytest.fixture
    def sample_event(self):
        """Create sample event."""
        return Event(
            event_type="SlideUpdated",
            deck_id=uuid4(),
            version=2,
            timestamp=datetime.now(),
            payload={"slide_id": "123", "status": "completed"},
        )

    @pytest.mark.asyncio
    async def test_publish_to_deck_channel_success(
        self, pubsub_manager, mock_redis_client, sample_event
    ):
        """Test successful publishing to deck channel."""
        _, mock_redis = mock_redis_client
        mock_redis.publish = AsyncMock()

        with patch(
            "app.core.observability.metrics.record_redis_operation"
        ) as mock_metrics:
            await pubsub_manager.publish_to_deck_channel(
                sample_event.deck_id, sample_event
            )

        # Verify publish was called
        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args

        expected_channel = f"{settings.redis_pubsub_key}:deck:{sample_event.deck_id}"
        assert call_args[0][0] == expected_channel

        # Parse the published data
        published_data = json.loads(call_args[0][1])
        assert published_data["event_type"] == "SlideUpdated"
        assert published_data["deck_id"] == str(sample_event.deck_id)
        assert published_data["version"] == 2

        mock_metrics.assert_called_with("pubsub_publish", "success")

    @pytest.mark.asyncio
    async def test_publish_to_deck_channel_redis_error(
        self, pubsub_manager, mock_redis_client, sample_event
    ):
        """Test publishing with Redis error."""
        _, mock_redis = mock_redis_client
        mock_redis.publish = AsyncMock(side_effect=RedisError("Publish failed"))

        with patch(
            "app.core.observability.metrics.record_redis_operation"
        ) as mock_metrics:
            with pytest.raises(MessagingException) as exc:
                await pubsub_manager.publish_to_deck_channel(
                    sample_event.deck_id, sample_event
                )

        assert "Channel publish failed" in str(exc.value)
        mock_metrics.assert_called_with("pubsub_publish", "error")

    @pytest.mark.asyncio
    async def test_subscribe_to_deck_channel_success(
        self, pubsub_manager, mock_redis_client, sample_event
    ):
        """Test successful subscription to deck channel."""
        _, mock_redis = mock_redis_client

        # Mock pubsub behavior
        mock_pubsub = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub

        # Create mock message
        event_data = {
            "event_type": sample_event.event_type,
            "deck_id": str(sample_event.deck_id),
            "version": sample_event.version,
            "timestamp": sample_event.timestamp.isoformat(),
            "payload": sample_event.payload,
        }

        mock_message = {"type": "message", "data": json.dumps(event_data)}

        # Mock async iterator
        async def mock_listen():
            yield mock_message

        mock_pubsub.listen.return_value = mock_listen()

        # Test subscription
        events = []
        async for event in pubsub_manager.subscribe_to_deck_channel(
            sample_event.deck_id
        ):
            events.append(event)
            break  # Break after first event to avoid infinite loop

        assert len(events) == 1
        event = events[0]
        assert event.event_type == sample_event.event_type
        assert event.deck_id == sample_event.deck_id
        assert event.version == sample_event.version

        # Verify pubsub subscribe was called
        expected_channel = f"{settings.redis_pubsub_key}:deck:{sample_event.deck_id}"
        mock_pubsub.subscribe.assert_called_once_with(expected_channel)

    @pytest.mark.asyncio
    async def test_subscribe_to_deck_channel_redis_error(
        self, pubsub_manager, mock_redis_client, sample_event
    ):
        """Test subscription with Redis error."""
        _, mock_redis = mock_redis_client
        mock_redis.pubsub.side_effect = RedisError("Pubsub error")

        with pytest.raises(MessagingException) as exc:
            async for _ in pubsub_manager.subscribe_to_deck_channel(
                sample_event.deck_id
            ):
                break

        assert "Pubsub subscription failed" in str(exc.value)


class TestRedisCacheManager:
    """Test cases for RedisCacheManager."""

    @pytest.fixture
    def mock_redis_client(self):
        """Create mock Redis client."""
        client = Mock()
        mock_redis = AsyncMock()
        client.get_client.return_value = mock_redis
        return client, mock_redis

    @pytest.fixture
    def cache_manager(self, mock_redis_client):
        """Create cache manager with mock."""
        client, _ = mock_redis_client
        return RedisCacheManager(client)

    @pytest.mark.asyncio
    async def test_set_cancellation_flag_success(
        self, cache_manager, mock_redis_client
    ):
        """Test successful cancellation flag setting."""
        _, mock_redis = mock_redis_client
        mock_redis.set = AsyncMock()

        deck_id = uuid4()

        with patch(
            "app.core.observability.metrics.record_redis_operation"
        ) as mock_metrics:
            await cache_manager.set_cancellation_flag(deck_id, ttl=1800)

        expected_key = f"cancel:deck:{deck_id}"
        mock_redis.set.assert_called_once_with(expected_key, "true", ex=1800)
        mock_metrics.assert_called_with("cache_set", "success")

    @pytest.mark.asyncio
    async def test_set_cancellation_flag_default_ttl(
        self, cache_manager, mock_redis_client
    ):
        """Test cancellation flag with default TTL."""
        _, mock_redis = mock_redis_client
        mock_redis.set = AsyncMock()

        deck_id = uuid4()
        await cache_manager.set_cancellation_flag(deck_id)

        expected_key = f"cancel:deck:{deck_id}"
        mock_redis.set.assert_called_once_with(expected_key, "true", ex=3600)

    @pytest.mark.asyncio
    async def test_set_cancellation_flag_redis_error(
        self, cache_manager, mock_redis_client
    ):
        """Test cancellation flag setting with Redis error."""
        _, mock_redis = mock_redis_client
        mock_redis.set = AsyncMock(side_effect=RedisError("Set failed"))

        deck_id = uuid4()

        with patch(
            "app.core.observability.metrics.record_redis_operation"
        ) as mock_metrics:
            with pytest.raises(MessagingException) as exc:
                await cache_manager.set_cancellation_flag(deck_id)

        assert "Cache set failed" in str(exc.value)
        mock_metrics.assert_called_with("cache_set", "error")

    @pytest.mark.asyncio
    async def test_check_cancellation_flag_exists(
        self, cache_manager, mock_redis_client
    ):
        """Test checking cancellation flag when it exists."""
        _, mock_redis = mock_redis_client
        mock_redis.get = AsyncMock(return_value="true")

        deck_id = uuid4()

        with patch(
            "app.core.observability.metrics.record_redis_operation"
        ) as mock_metrics:
            result = await cache_manager.check_cancellation_flag(deck_id)

        assert result is True
        expected_key = f"cancel:deck:{deck_id}"
        mock_redis.get.assert_called_once_with(expected_key)
        mock_metrics.assert_called_with("cache_get", "success")

    @pytest.mark.asyncio
    async def test_check_cancellation_flag_not_exists(
        self, cache_manager, mock_redis_client
    ):
        """Test checking cancellation flag when it doesn't exist."""
        _, mock_redis = mock_redis_client
        mock_redis.get = AsyncMock(return_value=None)

        deck_id = uuid4()
        result = await cache_manager.check_cancellation_flag(deck_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_cancellation_flag_redis_error(
        self, cache_manager, mock_redis_client
    ):
        """Test checking cancellation flag with Redis error."""
        _, mock_redis = mock_redis_client
        mock_redis.get = AsyncMock(side_effect=RedisError("Get failed"))

        deck_id = uuid4()

        with patch(
            "app.core.observability.metrics.record_redis_operation"
        ) as mock_metrics:
            result = await cache_manager.check_cancellation_flag(deck_id)

        assert result is False  # Default to not cancelled
        mock_metrics.assert_called_with("cache_get", "error")

    @pytest.mark.asyncio
    async def test_clear_cancellation_flag_success(
        self, cache_manager, mock_redis_client
    ):
        """Test successful cancellation flag clearing."""
        _, mock_redis = mock_redis_client
        mock_redis.delete = AsyncMock(return_value=1)

        deck_id = uuid4()

        with patch(
            "app.core.observability.metrics.record_redis_operation"
        ) as mock_metrics:
            await cache_manager.clear_cancellation_flag(deck_id)

        expected_key = f"cancel:deck:{deck_id}"
        mock_redis.delete.assert_called_once_with(expected_key)
        mock_metrics.assert_called_with("cache_delete", "success")

    @pytest.mark.asyncio
    async def test_clear_cancellation_flag_redis_error(
        self, cache_manager, mock_redis_client
    ):
        """Test cancellation flag clearing with Redis error."""
        _, mock_redis = mock_redis_client
        mock_redis.delete = AsyncMock(side_effect=RedisError("Delete failed"))

        deck_id = uuid4()

        with patch(
            "app.core.observability.metrics.record_redis_operation"
        ) as mock_metrics:
            await cache_manager.clear_cancellation_flag(deck_id)  # Should not raise

        mock_metrics.assert_called_with("cache_delete", "error")

    @pytest.mark.asyncio
    async def test_set_temporary_data_success(self, cache_manager, mock_redis_client):
        """Test successful temporary data setting."""
        _, mock_redis = mock_redis_client
        mock_redis.set = AsyncMock()

        test_data = {"status": "processing", "progress": 50}

        with patch(
            "app.core.observability.metrics.record_redis_operation"
        ) as mock_metrics:
            await cache_manager.set_temporary_data("test:key", test_data, ttl=1800)

        mock_redis.set.assert_called_once_with(
            "test:key", json.dumps(test_data), ex=1800
        )
        mock_metrics.assert_called_with("cache_set", "success")

    @pytest.mark.asyncio
    async def test_set_temporary_data_default_ttl(
        self, cache_manager, mock_redis_client
    ):
        """Test temporary data setting with default TTL."""
        _, mock_redis = mock_redis_client
        mock_redis.set = AsyncMock()

        test_data = {"status": "processing"}
        await cache_manager.set_temporary_data("test:key", test_data)

        mock_redis.set.assert_called_once_with(
            "test:key", json.dumps(test_data), ex=3600
        )

    @pytest.mark.asyncio
    async def test_set_temporary_data_redis_error(
        self, cache_manager, mock_redis_client
    ):
        """Test temporary data setting with Redis error."""
        _, mock_redis = mock_redis_client
        mock_redis.set = AsyncMock(side_effect=RedisError("Set failed"))

        test_data = {"status": "processing"}

        with patch(
            "app.core.observability.metrics.record_redis_operation"
        ) as mock_metrics:
            with pytest.raises(MessagingException) as exc:
                await cache_manager.set_temporary_data("test:key", test_data)

        assert "Cache set failed" in str(exc.value)
        mock_metrics.assert_called_with("cache_set", "error")

    @pytest.mark.asyncio
    async def test_get_temporary_data_success(self, cache_manager, mock_redis_client):
        """Test successful temporary data retrieval."""
        _, mock_redis = mock_redis_client
        test_data = {"status": "completed", "result": "success"}
        mock_redis.get = AsyncMock(return_value=json.dumps(test_data))

        with patch(
            "app.core.observability.metrics.record_redis_operation"
        ) as mock_metrics:
            result = await cache_manager.get_temporary_data("test:key")

        assert result == test_data
        mock_redis.get.assert_called_once_with("test:key")
        mock_metrics.assert_called_with("cache_get", "success")

    @pytest.mark.asyncio
    async def test_get_temporary_data_not_exists(
        self, cache_manager, mock_redis_client
    ):
        """Test temporary data retrieval when key doesn't exist."""
        _, mock_redis = mock_redis_client
        mock_redis.get = AsyncMock(return_value=None)

        result = await cache_manager.get_temporary_data("test:key")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_temporary_data_redis_error(
        self, cache_manager, mock_redis_client
    ):
        """Test temporary data retrieval with Redis error."""
        _, mock_redis = mock_redis_client
        mock_redis.get = AsyncMock(side_effect=RedisError("Get failed"))

        with patch(
            "app.core.observability.metrics.record_redis_operation"
        ) as mock_metrics:
            result = await cache_manager.get_temporary_data("test:key")

        assert result is None
        mock_metrics.assert_called_with("cache_get", "error")

    @pytest.mark.asyncio
    async def test_get_temporary_data_json_decode_error(
        self, cache_manager, mock_redis_client
    ):
        """Test temporary data retrieval with JSON decode error."""
        _, mock_redis = mock_redis_client
        mock_redis.get = AsyncMock(return_value="invalid json")

        with patch(
            "app.core.observability.metrics.record_redis_operation"
        ) as mock_metrics:
            result = await cache_manager.get_temporary_data("test:key")

        assert result is None
        mock_metrics.assert_called_with("cache_get", "error")
