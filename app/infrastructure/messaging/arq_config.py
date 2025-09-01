import logging
from typing import Any, Dict

from arq import cron
from arq.connections import RedisSettings

from app.core.config import settings
from app.application.tasks import (
    generate_deck,
    generate_slide,
    update_slide,
    cleanup_cancelled_decks,
)

# Configure logging for ARQ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def startup(ctx: Dict[str, Any]) -> None:
    """ARQ worker startup function."""
    logger.info("ARQ worker starting up")

    # Import here to avoid circular imports
    from app.infrastructure.db.database import Database
    from app.infrastructure.messaging.redis_client import RedisClient
    from app.infrastructure.llm.client import LLMClient

    # Initialize database
    database = Database(settings.database_url, echo=settings.database_echo)
    await database.initialize()
    ctx["database"] = database

    # Initialize Redis client
    redis_client = RedisClient(settings.redis_url)
    await redis_client.initialize()
    ctx["redis_client"] = redis_client

    # Initialize LLM client
    llm_client = LLMClient()
    await llm_client.initialize()
    ctx["llm_client"] = llm_client

    logger.info("ARQ worker startup complete")


async def shutdown(ctx: Dict[str, Any]) -> None:
    """ARQ worker shutdown function."""
    logger.info("ARQ worker shutting down")

    # Close database connections
    if "database" in ctx:
        await ctx["database"].close()

    # Close Redis connections
    if "redis_client" in ctx:
        await ctx["redis_client"].close()

    # Close LLM client
    if "llm_client" in ctx:
        await ctx["llm_client"].close()

    logger.info("ARQ worker shutdown complete")


async def heartbeat_task(ctx: Dict[str, Any]) -> None:
    """Periodic heartbeat task."""
    logger.debug("ARQ worker heartbeat")


async def test_task(ctx: Dict[str, Any]) -> str:
    """Simple test task to verify worker functionality."""
    logger.info("Test task executed successfully")
    return "Task completed successfully"


# Import task functions


# ARQ worker settings
class WorkerSettings:
    """ARQ worker configuration settings."""

    redis_settings = RedisSettings.from_dsn(settings.get_redis_arq_url())

    # Worker configuration
    max_jobs = settings.arq_max_jobs
    job_timeout = settings.arq_job_timeout
    max_tries = settings.arq_max_tries

    # Health check interval
    health_check_interval = 60

    # Startup and shutdown hooks
    on_startup = startup
    on_shutdown = shutdown

    # Periodic tasks
    cron_jobs = [
        cron(heartbeat_task, second=0, run_at_startup=False),  # Every minute
    ]

    # Job functions
    functions = [
        test_task,
        generate_deck,
        generate_slide,
        update_slide,
        cleanup_cancelled_decks,
    ]


# Create worker settings instance for easy access
worker_settings = WorkerSettings()
