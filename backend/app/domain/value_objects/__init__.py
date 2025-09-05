"""
Domain value objects - immutable objects that represent concepts.
"""

from .deck_status import DeckStatus
from .template_type import TemplateType, SlideTemplate

__all__ = ["DeckStatus", "TemplateType", "SlideTemplate"]
