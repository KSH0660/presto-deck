"""
Database configuration and session management.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.infra.config.settings import get_settings

# Eagerly initialize the engine and session factory
settings = get_settings()
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug_sql,
    pool_pre_ping=True,
    pool_recycle=300,
)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


def get_engine():
    """Get the database engine."""
    return engine


def get_session_factory():
    """Get the session factory."""
    return async_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database session.

    Yields an async database session and ensures proper cleanup.
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
