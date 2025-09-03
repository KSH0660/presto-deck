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
