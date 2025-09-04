"""
SQLAlchemy model for Deck Events (Event Sourcing).
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, UTC

import uuid

from app.data.models.base import Base


class EventModel(Base):
    __tablename__ = "deck_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deck_id = Column(
        UUID(as_uuid=True), ForeignKey("decks.id"), nullable=False, index=True
    )
    event_type = Column(String(50), nullable=False)  # DeckStarted, SlideCompleted, etc.
    event_data = Column(JSON, nullable=False)  # Full event payload
    created_at = Column(DateTime, default=datetime.now(UTC), nullable=False, index=True)

    # Relationships
    deck = relationship("DeckModel", back_populates="events")
