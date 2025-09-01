from typing import AsyncGenerator

from arq import ArqRedis
from fastapi import Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services import DeckService, SlideService
from app.core.security import security_service
from app.infrastructure.db.database import Database
from app.infrastructure.db.repositories import (
    PostgresDeckRepository,
    PostgresEventRepository,
    PostgresSlideRepository,
)
from app.infrastructure.messaging.redis_client import (
    RedisCacheManager,
    RedisClient,
    RedisStreamPublisher,
)

# Global instances (will be initialized in main.py)
database: Database = None
redis_client: RedisClient = None
arq_redis: ArqRedis = None


async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency."""
    if not database:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    async with database.session() as session:
        yield session


async def get_current_user_id(authorization: str | None = Header(None)) -> str:
    """Extract user ID from JWT token."""
    try:
        if not authorization:
            raise HTTPException(status_code=401, detail="Authorization header required")
        # Extract token from "Bearer <token>" format
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        token = authorization.split(" ")[1]
        user_id = security_service.extract_user_id_from_token(token)
        return user_id
        
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_deck_service(
    session: AsyncSession = Depends(get_database_session)
) -> DeckService:
    """Get deck service with dependencies."""
    if not redis_client or not arq_redis:
        raise HTTPException(status_code=500, detail="Redis not initialized")
    
    deck_repo = PostgresDeckRepository(session)
    slide_repo = PostgresSlideRepository(session)
    event_repo = PostgresEventRepository(session)
    stream_publisher = RedisStreamPublisher(redis_client)
    cache_manager = RedisCacheManager(redis_client)
    
    return DeckService(
        deck_repo=deck_repo,
        slide_repo=slide_repo,
        event_repo=event_repo,
        stream_publisher=stream_publisher,
        cache_manager=cache_manager,
        arq_redis=arq_redis,
    )


async def get_slide_service(
    session: AsyncSession = Depends(get_database_session)
) -> SlideService:
    """Get slide service with dependencies."""
    if not redis_client or not arq_redis:
        raise HTTPException(status_code=500, detail="Redis not initialized")
    
    slide_repo = PostgresSlideRepository(session)
    deck_repo = PostgresDeckRepository(session)
    event_repo = PostgresEventRepository(session)
    stream_publisher = RedisStreamPublisher(redis_client)
    
    return SlideService(
        slide_repo=slide_repo,
        deck_repo=deck_repo,
        event_repo=event_repo,
        stream_publisher=stream_publisher,
        arq_redis=arq_redis,
    )
