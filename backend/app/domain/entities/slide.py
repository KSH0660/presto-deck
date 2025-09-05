"""
Slide domain entity with core business rules.
"""

from dataclasses import dataclass
from typing import Optional
from uuid import UUID
from datetime import datetime


@dataclass
class Slide:
    id: Optional[UUID]
    deck_id: UUID
    order: int
    title: str
    content_outline: str
    html_content: Optional[str]
    presenter_notes: str
    template_filename: str  # Changed from TemplateType enum to string filename
    created_at: datetime
    updated_at: Optional[datetime] = None

    def is_complete(self) -> bool:
        """Business rule: slide is complete when it has HTML content."""
        return self.html_content is not None and len(self.html_content.strip()) > 0

    def can_be_edited(self) -> bool:
        """Business rule: slides can be edited until deck is completed."""
        return True  # For now, always editable

    def get_content_summary(self) -> str:
        """Business rule: provide summary for display purposes."""
        if self.html_content:
            # Strip HTML tags for summary
            import re

            clean_text = re.sub(r"<[^>]+>", "", self.html_content)
            return clean_text[:200] + "..." if len(clean_text) > 200 else clean_text
        return (
            self.content_outline[:200] + "..."
            if len(self.content_outline) > 200
            else self.content_outline
        )

    def update_content(self, html_content: str, presenter_notes: str = None) -> None:
        """
        Business rule: Update slide content with validation.

        Args:
            html_content: New HTML content for the slide
            presenter_notes: Optional presenter notes

        Raises:
            ValueError: If content is invalid
        """
        if not html_content or not html_content.strip():
            raise ValueError("HTML content cannot be empty")

        self.html_content = html_content.strip()
        if presenter_notes is not None:
            self.presenter_notes = presenter_notes
        self.updated_at = datetime.utcnow()

    def change_order(self, new_order: int) -> None:
        """
        Business rule: Change slide order with validation.

        Args:
            new_order: New order value (must be positive)

        Raises:
            ValueError: If order is invalid
        """
        if new_order <= 0:
            raise ValueError("Slide order must be positive")

        self.order = new_order
        self.updated_at = datetime.utcnow()
