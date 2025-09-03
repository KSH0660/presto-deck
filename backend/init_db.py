#!/usr/bin/env python3
"""
Initialize database tables for development.
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from app.data.models.base import Base
from app.infra.config.settings import get_settings


async def init_db():
    """Create all database tables."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()
    print("Database tables created successfully!")


if __name__ == "__main__":
    asyncio.run(init_db())
