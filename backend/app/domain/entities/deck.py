"""
Deck domain entity with core business rules.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime

from app.domain.value_objects.deck_status import DeckStatus
from app.domain.value_objects.template_type import TemplateType


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
        """Business rule: only certain statuses can be cancelled."""
        return self.status.can_be_cancelled()

    def mark_as_completed(self):
        """Business rule: mark deck as completed with timestamp."""
        if not self.status.can_transition_to(DeckStatus.COMPLETED):
            raise ValueError(f"Cannot complete deck from {self.status.value} status")

        self.status = DeckStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def transition_to_status(self, new_status: DeckStatus) -> None:
        """
        Business rule: Transition to new status if valid.

        Args:
            new_status: The status to transition to

        Raises:
            ValueError: If transition is not allowed
        """
        if not self.status.can_transition_to(new_status):
            raise ValueError(
                f"Invalid status transition from {self.status.value} to {new_status.value}"
            )

        self.status = new_status
        self.updated_at = datetime.utcnow()

    def is_processing(self) -> bool:
        """Business rule: check if deck is actively being processed."""
        return self.status.is_processing()

    def increment_slide_count(self):
        """Business rule: increment slide count when new slide is added."""
        if self.slide_count >= 50:  # Business constraint
            raise ValueError("Maximum 50 slides per deck")

        self.slide_count += 1
        self.updated_at = datetime.utcnow()
