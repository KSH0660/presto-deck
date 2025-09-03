"""
Redis client for caching and state management.
"""

import redis.asyncio as redis
from app.infra.config.settings import get_settings
from app.infra.config.logging_config import get_logger


async def get_redis_client() -> redis.Redis:
    """Get Redis client for caching and state management."""
    settings = get_settings()
    logger = get_logger("infra.redis")
    client = redis.from_url(settings.redis_url)
    logger.info("redis.client.get", url=settings.redis_url)
    return client
