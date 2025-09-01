import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, database_url: str, echo: bool = False) -> None:
        self.database_url = database_url
        self.echo = echo
        self.engine = None
        self.async_session_maker = None

    async def initialize(self) -> None:
        logger.info("Initializing database connection")
        self.engine = create_async_engine(
            self.database_url,
            echo=self.echo,
            future=True,
            poolclass=NullPool if "pytest" in self.database_url else None,
        )
        self.async_session_maker = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
        logger.info("Database connection initialized")

    async def close(self) -> None:
        if self.engine:
            logger.info("Closing database connection")
            await self.engine.dispose()
            logger.info("Database connection closed")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        if not self.async_session_maker:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def health_check(self) -> bool:
        try:
            async with self.session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False