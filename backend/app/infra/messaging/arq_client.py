"""
ARQ client for background job queuing.
"""

from typing import Dict, Any, Optional
from arq import create_pool
from arq.connections import RedisSettings


class ARQClient:
    def __init__(self, redis_settings: RedisSettings):
        self.redis_settings = redis_settings
        self._pool = None

    async def get_pool(self):
        """Get or create Redis connection pool."""
        if self._pool is None:
            self._pool = await create_pool(self.redis_settings)
        return self._pool

    async def enqueue(self, function_name: str, *args, **kwargs) -> str:
        """Enqueue a background job."""
        pool = await self.get_pool()
        job = await pool.enqueue_job(function_name, *args, **kwargs)
        return job.job_id

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status and result."""
        pool = await self.get_pool()
        job = await pool.get_job(job_id)

        if not job:
            return None

        return {
            "job_id": job.job_id,
            "status": job.status.name if job.status else "unknown",
            "result": job.result,
            "enqueue_time": job.enqueue_time.isoformat() if job.enqueue_time else None,
            "start_time": job.start_time.isoformat() if job.start_time else None,
            "finish_time": job.finish_time.isoformat() if job.finish_time else None,
        }

    async def close(self):
        """Close Redis connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None


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
