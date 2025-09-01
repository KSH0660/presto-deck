import enum
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.types import TypeDecorator, CHAR
from uuid import uuid4
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class GUID(TypeDecorator):
    """Platform-independent GUID type."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PostgresUUID())
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, str):
                return "%.32x" % int(value.hex, 16)
            else:
                return "%.32x" % int(value.replace('-', ''), 16)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, str):
                return str(value)
            return value


class DeckStatusEnum(enum.Enum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class DeckModel(Base):
    __tablename__ = "decks"

    id = Column(GUID(), primary_key=True, default=uuid4)
    user_id = Column(String(255), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    status = Column(Enum(DeckStatusEnum), nullable=False, default=DeckStatusEnum.PENDING, index=True)
    version = Column(Integer, nullable=False, default=1)
    deck_plan = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    slides = relationship("SlideModel", back_populates="deck", cascade="all, delete-orphan")
    events = relationship("DeckEventModel", back_populates="deck", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<DeckModel(id={self.id}, title='{self.title}', status='{self.status.value}')>"


class SlideModel(Base):
    __tablename__ = "slides"

    id = Column(GUID(), primary_key=True, default=uuid4)
    deck_id = Column(GUID(), ForeignKey("decks.id", ondelete="CASCADE"), nullable=False, index=True)
    slide_order = Column(Integer, nullable=False)
    html_content = Column(Text, nullable=False)
    presenter_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    deck = relationship("DeckModel", back_populates="slides")

    __table_args__ = (
        UniqueConstraint("deck_id", "slide_order", name="uq_deck_slide_order"),
    )

    def __repr__(self) -> str:
        return f"<SlideModel(id={self.id}, deck_id={self.deck_id}, order={self.slide_order})>"


class DeckEventModel(Base):
    __tablename__ = "deck_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    deck_id = Column(GUID(), ForeignKey("decks.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    event_type = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    deck = relationship("DeckModel", back_populates="events")

    def __repr__(self) -> str:
        return f"<DeckEventModel(id={self.id}, deck_id={self.deck_id}, event_type='{self.event_type}', version={self.version})>"