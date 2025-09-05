"""
ARQ client for background job queuing.
"""

from typing import Dict, Any, Optional
from arq import create_pool
from arq.connections import RedisSettings
import redis.asyncio as redis
from app.infra.config.logging_config import get_logger
from app.application.ports import MessageBrokerPort


class ARQClient(MessageBrokerPort):
    def __init__(self, redis_settings: RedisSettings):
        self.redis_settings = redis_settings
        self._pool = None
        self._redis_client = None
        self._log = get_logger("infra.arq")

    async def get_pool(self):
        """Get or create Redis connection pool."""
        if self._pool is None:
            self._pool = await create_pool(self.redis_settings)
            self._log.info(
                "arq.pool.created",
                host=self.redis_settings.host,
                port=self.redis_settings.port,
                database=self.redis_settings.database,
            )
        return self._pool

    async def get_redis_client(self):
        """Get or create Redis client for pub/sub operations."""
        if self._redis_client is None:
            self._redis_client = redis.Redis(
                host=self.redis_settings.host,
                port=self.redis_settings.port,
                db=self.redis_settings.database,
                decode_responses=True,
            )
        return self._redis_client

    async def enqueue_job(self, job_name: str, **kwargs) -> str:
        """Enqueue a background job."""
        pool = await self.get_pool()
        job = await pool.enqueue_job(job_name, **kwargs)
        self._log.info("arq.enqueue_job", job_name=job_name, job_id=job.job_id)
        return job.job_id

    async def enqueue(self, function_name: str, *args, **kwargs) -> str:
        """Legacy method for backward compatibility."""
        return await self.enqueue_job(function_name, **kwargs)

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status and result."""
        pool = await self.get_pool()
        job = await pool.get_job(job_id)

        if not job:
            return None

        result = {
            "job_id": job.job_id,
            "status": job.status.name if job.status else "unknown",
            "result": job.result,
            "enqueue_time": job.enqueue_time.isoformat() if job.enqueue_time else None,
            "start_time": job.start_time.isoformat() if job.start_time else None,
            "finish_time": job.finish_time.isoformat() if job.finish_time else None,
        }
        self._log.info("arq.job.status", job_id=job_id, status=result["status"])
        return result

    async def publish_event(self, channel: str, event_data: Dict[str, Any]) -> None:
        """Publish an event to a channel."""
        redis_client = await self.get_redis_client()
        import json

        serialized_data = json.dumps(event_data)
        await redis_client.publish(channel, serialized_data)
        self._log.info(
            "arq.publish_event",
            channel=channel,
            event_type=event_data.get("type", "unknown"),
        )

    async def close(self):
        """Close Redis connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._log.info("arq.pool.closed")
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None
            self._log.info("arq.redis_client.closed")


async def get_arq_client() -> ARQClient:
    """Dependency for ARQ client."""
    from app.infra.config.settings import get_settings

    settings = get_settings()
    redis_settings = RedisSettings(
        host=settings.arq_redis_host,
        port=settings.arq_redis_port,
        database=settings.arq_redis_database,
    )
    return ARQClient(redis_settings)
