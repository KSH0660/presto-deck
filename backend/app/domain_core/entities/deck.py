"""
Deck domain entity with core business rules.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime

from app.domain_core.value_objects.deck_status import DeckStatus
from app.domain_core.value_objects.template_type import TemplateType


@dataclass
class Deck:
    id: UUID
    user_id: UUID
    prompt: str
    status: DeckStatus
    style_preferences: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    slide_count: int = 0
    template_type: Optional[TemplateType] = None

    def can_be_cancelled(self) -> bool:
        """Business rule: only pending/planning decks can be cancelled."""
        return self.status in [DeckStatus.PENDING, DeckStatus.PLANNING]

    def mark_as_completed(self):
        """Business rule: mark deck as completed with timestamp."""
        if self.status != DeckStatus.GENERATING:
            raise ValueError("Can only complete decks that are generating")

        self.status = DeckStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def increment_slide_count(self):
        """Business rule: increment slide count when new slide is added."""
        if self.slide_count >= 50:  # Business constraint
            raise ValueError("Maximum 50 slides per deck")

        self.slide_count += 1
        self.updated_at = datetime.utcnow()
