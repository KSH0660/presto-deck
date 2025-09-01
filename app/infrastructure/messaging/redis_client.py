import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Callable, Union
from uuid import UUID

import redis.asyncio as redis
import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.api.schemas import Event
from app.core.config import settings
from app.core.observability import metrics
from app.domain.exceptions import MessagingException

logger = structlog.get_logger(__name__)


class RedisClient:
    """Redis client manager for connection pooling and operations."""

    def __init__(self, redis_url: str) -> None:
        self.redis_url = redis_url
        self.pool: Optional[redis.ConnectionPool] = None
        self.redis_client: Optional[Redis] = None

    async def initialize(self) -> None:
        """Initialize Redis connection pool."""
        try:
            self.pool = redis.ConnectionPool.from_url(
                self.redis_url,
                decode_responses=True,
                max_connections=20,
                health_check_interval=30,
            )
            self.redis_client = Redis(connection_pool=self.pool)

            # Test connection
            await self.redis_client.ping()
            logger.info("Redis connection initialized", url=self.redis_url)
        except Exception as e:
            logger.error("Failed to initialize Redis connection", error=str(e))
            raise MessagingException(f"Redis initialization failed: {e}")

    async def close(self) -> None:
        """Close Redis connections."""
        client = self.redis_client
        if not client:
            return

        # prefer close() for compatibility with AsyncMock/specs; fallback to aclose()/wait_closed()
        aclose_method = getattr(client, "aclose", None)
        if aclose_method is not None:
            res = aclose_method()
            if asyncio.iscoroutine(res):
                await res
        else:
            close_method = getattr(client, "close", None)
            if close_method is not None:
                res = close_method()
                if asyncio.iscoroutine(res):
                    await res
            wait_closed = getattr(client, "wait_closed", None)
            if wait_closed is not None:
                res = wait_closed()
                if asyncio.iscoroutine(res):
                    await res

        self.redis_client = None
        logger.info("Redis connection closed")

    async def health_check(self) -> bool:
        """Check Redis connection health."""
        try:
            if not self.redis_client:
                return False
            await self.redis_client.ping()
            return True
        except Exception as e:
            logger.error("Redis health check failed", error=str(e))
            return False

    def get_client(self) -> Redis:
        """Get Redis client instance."""
        if not self.redis_client:
            raise MessagingException("Redis client not initialized")
        return self.redis_client


class RedisStreamPublisher:
    def __init__(self, redis_client: RedisClient) -> None:
        self.redis_client = redis_client
        self.stream_key = settings.redis_stream_key

    async def publish_event(self, event: Event) -> str:
        """Publish event to Redis Stream."""
        try:
            client = self.redis_client.get_client()

            # Convert event to dict for Redis
            event_data = {
                "event_type": event.event_type,
                "deck_id": str(event.deck_id),
                "version": str(event.version),
                "timestamp": event.timestamp.isoformat(),
                "payload": json.dumps(event.payload),
            }

            # Add to stream
            stream_id = await client.xadd(self.stream_key, event_data)

            logger.info(
                "Event published to stream",
                stream_id=stream_id,
                event_type=event.event_type,
                deck_id=str(event.deck_id),
            )

            metrics.record_redis_operation("stream_publish", "success")
            return stream_id

        except RedisError as e:
            logger.error("Failed to publish event to stream", error=str(e))
            metrics.record_redis_operation("stream_publish", "error")
            raise MessagingException(f"Stream publish failed: {e}")


class RedisStreamConsumer:
    """Consume events from Redis Stream using consumer groups."""

    def __init__(
        self, redis_client: RedisClient, consumer_group: str, consumer_name: str
    ) -> None:
        self.redis_client = redis_client
        self.stream_key = settings.redis_stream_key
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name

    async def create_consumer_group(self) -> None:
        """Create consumer group if it doesn't exist."""
        try:
            client = self.redis_client.get_client()
            await client.xgroup_create(
                name=self.stream_key,
                groupname=self.consumer_group,
                id="0",
                mkstream=True,
            )
            logger.info("Consumer group created", group=self.consumer_group)
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.debug("Consumer group already exists", group=self.consumer_group)
            else:
                raise MessagingException(f"Failed to create consumer group: {e}")

    async def consume_events(
        self,
        handler: Callable[[Event], None],
        batch_size: int = 10,
        block_ms: int = 1000,
    ) -> None:
        """Consume events from Redis Stream with consumer group."""
        await self.create_consumer_group()
        client = self.redis_client.get_client()

        logger.info(
            "Starting event consumer",
            group=self.consumer_group,
            consumer=self.consumer_name,
        )

        while True:
            try:
                # Read from stream
                messages = await client.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.consumer_name,
                    streams={self.stream_key: ">"},
                    count=batch_size,
                    block=block_ms,
                )

                if messages:
                    for stream_name, stream_messages in messages:
                        for message_id, fields in stream_messages:
                            try:
                                # Parse event
                                event = self._parse_event(fields)

                                # Process event
                                await handler(event)

                                # Acknowledge message
                                await client.xack(
                                    self.stream_key, self.consumer_group, message_id
                                )

                                metrics.record_redis_operation(
                                    "stream_consume", "success"
                                )

                            except Exception as e:
                                logger.error(
                                    "Error processing stream message",
                                    message_id=message_id,
                                    error=str(e),
                                )
                                metrics.record_redis_operation(
                                    "stream_consume", "error"
                                )

            except Exception as e:
                logger.error("Stream consumer error", error=str(e))
                await asyncio.sleep(5)  # Wait before retrying

    def _parse_event(self, fields: Dict[str, str]) -> Event:
        """Parse event from Redis stream fields."""
        return Event(
            event_type=fields["event_type"],
            deck_id=UUID(fields["deck_id"]),
            version=int(fields["version"]),
            timestamp=fields["timestamp"],
            payload=json.loads(fields["payload"]) if fields.get("payload") else {},
        )


class RedisPubSubManager:
    def __init__(self, redis_client: RedisClient) -> None:
        self.redis_client = redis_client
        self.pubsub_key_prefix = settings.redis_pubsub_key

    async def publish_to_deck_channel(self, deck_id: UUID, event: Event) -> None:
        """Publish event to deck-specific channel."""
        try:
            client = self.redis_client.get_client()
            channel = f"{self.pubsub_key_prefix}:deck:{deck_id}"

            event_data = {
                "event_type": event.event_type,
                "deck_id": str(event.deck_id),
                "version": event.version,
                "timestamp": event.timestamp.isoformat(),
                "payload": event.payload,
            }

            await client.publish(channel, json.dumps(event_data))

            logger.debug(
                "Event published to channel",
                channel=channel,
                event_type=event.event_type,
            )

            metrics.record_redis_operation("pubsub_publish", "success")

        except RedisError as e:
            logger.error("Failed to publish to channel", error=str(e))
            metrics.record_redis_operation("pubsub_publish", "error")
            raise MessagingException(f"Channel publish failed: {e}")

    async def subscribe_to_deck_channel(self, deck_id: UUID) -> AsyncIterator[Event]:
        """Subscribe to deck-specific channel."""
        try:
            client = self.redis_client.get_client()
            channel = f"{self.pubsub_key_prefix}:deck:{deck_id}"

            pubsub = client.pubsub()
            if asyncio.iscoroutine(pubsub):
                pubsub = await pubsub
            await pubsub.subscribe(channel)

            logger.info("Subscribed to deck channel", channel=channel)

            try:
                listener = pubsub.listen()
                if asyncio.iscoroutine(listener):
                    listener = await listener
                async for message in listener:
                    if message["type"] == "message":
                        try:
                            event_data = json.loads(message["data"])
                            event = Event(
                                event_type=event_data["event_type"],
                                deck_id=UUID(event_data["deck_id"]),
                                version=event_data["version"],
                                timestamp=event_data["timestamp"],
                                payload=event_data.get("payload", {}),
                            )
                            yield event

                        except Exception as e:
                            logger.error(
                                "Error parsing pubsub message",
                                message=message,
                                error=str(e),
                            )
            finally:
                await pubsub.unsubscribe(channel)
                # Prefer close() for compatibility with tests/mocks; fallback to aclose()
                aclose_method = getattr(pubsub, "aclose", None)
                if aclose_method is not None:
                    res = aclose_method()
                    if asyncio.iscoroutine(res):
                        await res
                else:
                    close_method = getattr(pubsub, "close", None)
                    if close_method is not None:
                        res = close_method()
                        if asyncio.iscoroutine(res):
                            await res

        except RedisError as e:
            logger.error("Pubsub subscription error", error=str(e))
            raise MessagingException(f"Pubsub subscription failed: {e}")


class RedisCacheManager:
    def __init__(self, redis_client: RedisClient) -> None:
        self.redis_client = redis_client

    async def set_cancellation_flag(self, deck_id: UUID, ttl: int = 3600) -> None:
        """Set cancellation flag for deck generation."""
        try:
            client = self.redis_client.get_client()
            key = f"cancel:deck:{deck_id}"
            await client.set(key, "true", ex=ttl)

            logger.info("Cancellation flag set", deck_id=str(deck_id))
            metrics.record_redis_operation("cache_set", "success")

        except RedisError as e:
            logger.error("Failed to set cancellation flag", error=str(e))
            metrics.record_redis_operation("cache_set", "error")
            raise MessagingException(f"Cache set failed: {e}")

    async def check_cancellation_flag(self, deck_id: UUID) -> bool:
        """Check if deck generation should be cancelled."""
        try:
            client = self.redis_client.get_client()
            key = f"cancel:deck:{deck_id}"
            result = await client.get(key)

            metrics.record_redis_operation("cache_get", "success")
            return result is not None

        except RedisError as e:
            logger.error("Failed to check cancellation flag", error=str(e))
            metrics.record_redis_operation("cache_get", "error")
            return False  # Default to not cancelled on error

    async def clear_cancellation_flag(self, deck_id: UUID) -> None:
        """Clear cancellation flag."""
        try:
            client = self.redis_client.get_client()
            key = f"cancel:deck:{deck_id}"
            await client.delete(key)

            logger.debug("Cancellation flag cleared", deck_id=str(deck_id))
            metrics.record_redis_operation("cache_delete", "success")

        except RedisError as e:
            logger.error("Failed to clear cancellation flag", error=str(e))
            metrics.record_redis_operation("cache_delete", "error")

    async def set_temporary_data(
        self, key: str, data: Dict[str, Any], ttl: int = 3600
    ) -> None:
        """Set temporary data with TTL."""
        try:
            client = self.redis_client.get_client()
            await client.set(key, json.dumps(data), ex=ttl)

            metrics.record_redis_operation("cache_set", "success")

        except RedisError as e:
            logger.error("Failed to set temporary data", key=key, error=str(e))
            metrics.record_redis_operation("cache_set", "error")
            raise MessagingException(f"Cache set failed: {e}")

    async def get_temporary_data(self, key: str) -> Optional[Dict[str, Any]]:
        """Get temporary data."""
        try:
            client = self.redis_client.get_client()
            result = await client.get(key)

            metrics.record_redis_operation("cache_get", "success")

            if result:
                return json.loads(result)
            return None

        except (RedisError, json.JSONDecodeError) as e:
            logger.error("Failed to get temporary data", key=key, error=str(e))
            metrics.record_redis_operation("cache_get", "error")
            return None
