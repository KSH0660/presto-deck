from datetime import datetime, UTC
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class DeckStatus(str, Enum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Deck(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: str
    title: str
    status: DeckStatus = DeckStatus.PENDING
    version: int = 1
    deck_plan: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode='after')
    def sync_timestamps(self):
        if hasattr(self, '_initial_creation') and self._initial_creation:
            return self
        # If both timestamps are default (very close to each other), sync them
        if abs((self.created_at - self.updated_at).total_seconds()) < 0.01:
            self.updated_at = self.created_at
        return self

    def can_be_cancelled(self) -> bool:
        return self.status in {
            DeckStatus.PENDING,
            DeckStatus.PLANNING,
            DeckStatus.GENERATING,
        }

    def can_be_modified(self) -> bool:
        return self.status in {
            DeckStatus.PENDING,
            DeckStatus.PLANNING,
            DeckStatus.GENERATING,
            DeckStatus.COMPLETED,
        }

    def is_in_progress(self) -> bool:
        return self.status in {
            DeckStatus.PENDING,
            DeckStatus.PLANNING,
            DeckStatus.GENERATING,
        }

    def increment_version(self) -> None:
        self.version += 1
        self.updated_at = datetime.now(UTC)

    def update_status(self, status: DeckStatus) -> None:
        self.status = status
        self.increment_version()

    def update_plan(self, plan: Dict[str, Any]) -> None:
        self.deck_plan = plan
        self.increment_version()

    def __eq__(self, other) -> bool:
        if not isinstance(other, Deck):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


class Slide(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    deck_id: UUID
    slide_order: int
    html_content: str
    presenter_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode='after')
    def sync_timestamps(self):
        if hasattr(self, '_initial_creation') and self._initial_creation:
            return self
        # If both timestamps are default (very close to each other), sync them
        if abs((self.created_at - self.updated_at).total_seconds()) < 0.01:
            self.updated_at = self.created_at
        return self

    def update_content(self, html_content: str, presenter_notes: Optional[str] = None) -> None:
        self.html_content = html_content
        if presenter_notes is not None:
            self.presenter_notes = presenter_notes
        self.updated_at = datetime.now(UTC)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Slide):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


class DeckEvent(BaseModel):
    id: Optional[int] = None
    deck_id: UUID
    version: int
    event_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))