"""
Unit of Work pattern implementation for transaction boundaries.
"""

from sqlalchemy.ext.asyncio import AsyncSession


class UnitOfWork:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.rollback()
        elif not self._committed:
            await self.rollback()

    async def commit(self):
        """Commit the transaction."""
        await self.session.commit()
        self._committed = True

    async def rollback(self):
        """Rollback the transaction."""
        await self.session.rollback()
