"""
ARQ worker for background job processing.
"""

from uuid import UUID
from arq.connections import RedisSettings
from app.infra.config.settings import get_settings
from app.infra.config.logging_config import get_logger
from app.application.jobs.generate_deck_plan_job import GenerateDeckPlanJob
from app.infra.config.database import async_session_factory
from app.data.repositories.deck_repository import DeckRepository
from app.data.repositories.slide_repository import SlideRepository
from app.data.repositories.event_repository import EventRepository
from app.application.unit_of_work import UnitOfWork
from app.infra.config.dependencies import get_llm_client, get_websocket_broadcaster


async def generate_deck_plan(
    ctx, deck_id: str, user_id: str, prompt: str, style_preferences: dict = None
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

        # Create dependencies with proper session management
        async with async_session_factory() as db_session:
            try:
                uow = UnitOfWork(db_session)
                deck_repo = DeckRepository(db_session)
                slide_repo = SlideRepository(db_session)
                event_repo = EventRepository(db_session)
                llm_client = await get_llm_client()
                ws_broadcaster = await get_websocket_broadcaster()

                # Create and execute job
                job = GenerateDeckPlanJob(
                    uow=uow,
                    deck_repo=deck_repo,
                    slide_repo=slide_repo,
                    event_repo=event_repo,
                    ws_broadcaster=ws_broadcaster,
                    llm_client=llm_client,
                )

                await job.execute(
                    deck_id=UUID(deck_id),
                    user_id=UUID(user_id),
                    prompt=prompt,
                    style_preferences=style_preferences,
                )
            except Exception:
                await db_session.rollback()
                raise

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
