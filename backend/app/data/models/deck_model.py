"""
SQLAlchemy model for Deck entity.
"""

from sqlalchemy import Column, String, Text, Integer, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.data.models.base import Base


class DeckModel(Base):
    __tablename__ = "decks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    prompt = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    style_preferences = Column(JSON, nullable=True)
    template_type = Column(String(50), nullable=True)
    slide_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    slides = relationship(
        "SlideModel", back_populates="deck", cascade="all, delete-orphan"
    )
