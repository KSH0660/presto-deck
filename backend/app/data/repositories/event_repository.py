"""
Event repository for storing deck events.
"""

from typing import Dict, Any, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.data.models.event_model import EventModel
from app.infra.config.logging_config import get_logger


class EventRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._log = get_logger("repo.event")

    async def store_event(self, deck_id: UUID, event_data: Dict[str, Any]) -> None:
        """Store a deck event."""
        event_model = EventModel(
            deck_id=deck_id,
            event_type=event_data["type"],
            event_data=event_data,
            created_at=datetime.now(),
        )

        self.session.add(event_model)
        await self.session.flush()
        self._log.info(
            "event.store", deck_id=str(deck_id), event_type=event_data.get("type")
        )

    async def get_events_by_deck_id(self, deck_id: UUID) -> List[Dict[str, Any]]:
        """Get all events for a deck ordered by creation time."""
        result = await self.session.execute(
            select(EventModel)
            .where(EventModel.deck_id == deck_id)
            .order_by(EventModel.created_at)
        )
        event_models = result.scalars().all()

        items = [model.event_data for model in event_models]
        self._log.info("event.list", deck_id=str(deck_id), count=len(items))
        return items

    async def get_events_since_version(
        self, deck_id: UUID, since_version: int
    ) -> List[Dict[str, Any]]:
        """Get events since a specific version for replay."""
        result = await self.session.execute(
            select(EventModel)
            .where(
                EventModel.deck_id == deck_id,
                EventModel.event_data["version"].astext.cast(int) > since_version,
            )
            .order_by(EventModel.created_at)
        )
        event_models = result.scalars().all()

        items = [model.event_data for model in event_models]
        self._log.info(
            "event.list.since",
            deck_id=str(deck_id),
            since_version=since_version,
            count=len(items),
        )
        return items
