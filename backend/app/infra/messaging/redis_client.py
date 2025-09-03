"""
Redis client for caching and state management.
"""

import redis.asyncio as redis
from app.infra.config.settings import get_settings


async def get_redis_client() -> redis.Redis:
    """Get Redis client for caching and state management."""
    settings = get_settings()
    return redis.from_url(settings.redis_url)
