"""
ARQ worker for background job processing.
"""

from arq.connections import RedisSettings
from app.infra.config.settings import get_settings
from app.infra.config.logging_config import get_logger

# Import use cases that will be called as background jobs


async def generate_deck_plan(
    deck_id: str, user_id: str, prompt: str, style_preferences: dict = None
):
    """Background task for deck plan creation."""
    log = get_logger("worker.create_deck_plan")
    log.info("task.start", deck_id=deck_id)

    try:
        log.info(
            "task.start",
            deck_id=deck_id,
            user_id=user_id,
            prompt_len=len(prompt) if prompt else 0,
        )

        # TODO: Implement the actual deck plan generation logic
        # This would call the GenerateDeckPlanUseCase with LLM integration

        log.info("task.completed", deck_id=deck_id)

    except Exception as e:
        log.error("task.failed", deck_id=deck_id, error=str(e))
        raise


# Worker settings
def get_worker_settings():
    settings = get_settings()
    return {
        "redis_settings": RedisSettings(
            host=settings.arq_redis_host,
            port=settings.arq_redis_port,
            database=settings.arq_redis_database,
        ),
        "functions": [
            generate_deck_plan,
        ],
        "worker_name": "presto-deck-worker",
        "max_jobs": 10,
        "job_timeout": 300,  # 5 minutes
    }


# For ARQ CLI
WorkerSettings = get_worker_settings()
