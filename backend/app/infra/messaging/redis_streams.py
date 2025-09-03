"""
Redis Streams for event streaming and replay.
"""

from typing import Dict, Any, List, Optional
import json
from datetime import datetime
import redis.asyncio as redis


class RedisStreamClient:
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client

    async def add_event(self, deck_id: str, event_data: Dict[str, Any]) -> str:
        """Add event to Redis Stream for a deck."""
        stream_name = f"deck_events:{deck_id}"

        # Serialize event data
        serialized_data = {
            key: json.dumps(value) if isinstance(value, (dict, list)) else str(value)
            for key, value in event_data.items()
        }

        # Add timestamp if not present
        if "timestamp" not in serialized_data:
            serialized_data["timestamp"] = datetime.utcnow().isoformat()

        # Add to stream
        message_id = await self.redis_client.xadd(stream_name, serialized_data)

        return message_id

    async def read_events(
        self, deck_id: str, since_id: str = "0-0", count: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Read events from Redis Stream since a specific ID."""
        stream_name = f"deck_events:{deck_id}"

        # Read from stream
        result = await self.redis_client.xread(
            {stream_name: since_id},
            count=count,
            block=0,  # Don't block, return immediately
        )

        events = []
        if result:
            for stream, messages in result:
                for message_id, fields in messages:
                    # Deserialize event data
                    event_data = {}
                    for key, value in fields.items():
                        key_str = key.decode() if isinstance(key, bytes) else key
                        value_str = (
                            value.decode() if isinstance(value, bytes) else value
                        )

                        # Try to parse JSON, fallback to string
                        try:
                            event_data[key_str] = json.loads(value_str)
                        except (json.JSONDecodeError, TypeError):
                            event_data[key_str] = value_str

                    event_data["_message_id"] = (
                        message_id.decode()
                        if isinstance(message_id, bytes)
                        else message_id
                    )
                    events.append(event_data)

        return events

    async def get_latest_event_id(self, deck_id: str) -> Optional[str]:
        """Get the latest event ID for a deck stream."""
        stream_name = f"deck_events:{deck_id}"

        try:
            # Get stream info
            info = await self.redis_client.xinfo_stream(stream_name)
            return info.get("last-generated-id")
        except redis.ResponseError:
            # Stream doesn't exist yet
            return None

    async def delete_stream(self, deck_id: str) -> bool:
        """Delete entire event stream for a deck."""
        stream_name = f"deck_events:{deck_id}"
        return await self.redis_client.delete(stream_name) > 0

    async def trim_stream(self, deck_id: str, max_length: int = 1000):
        """Trim stream to maximum length to save memory."""
        stream_name = f"deck_events:{deck_id}"
        await self.redis_client.xtrim(stream_name, maxlen=max_length, approximate=True)
