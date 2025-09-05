"""
Unit of Work pattern implementation for transaction boundaries.

The Unit of Work pattern maintains a list of objects affected by a business transaction
and coordinates writing out changes and resolving concurrency problems.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports import (
    DeckRepositoryPort,
    SlideRepositoryPort,
    EventRepositoryPort,
)


class UnitOfWork:
    """
    Unit of Work implementation that manages transaction boundaries
    and provides access to repositories within a transaction context.
    """

    def __init__(
        self,
        session: AsyncSession,
        deck_repo: DeckRepositoryPort,
        slide_repo: SlideRepositoryPort,
        event_repo: EventRepositoryPort,
    ):
        self.session = session
        self.deck_repo = deck_repo
        self.slide_repo = slide_repo
        self.event_repo = event_repo
        self._committed = False

    async def __aenter__(self):
        """Enter transaction context."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit transaction context with cleanup."""
        if exc_type is not None:
            await self.rollback()
        elif not self._committed:
            await self.rollback()

    async def commit(self):
        """
        Commit the transaction.

        This makes all changes within the transaction permanent.
        """
        await self.session.commit()
        self._committed = True

    async def rollback(self):
        """
        Rollback the transaction.

        This discards all changes made within the transaction.
        """
        await self.session.rollback()

    @property
    def is_committed(self) -> bool:
        """Check if the transaction has been committed."""
        return self._committed
