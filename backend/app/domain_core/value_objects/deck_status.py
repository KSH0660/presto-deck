"""
Deck status value object.
"""

from enum import Enum


class DeckStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    GENERATING = "generating"
    EDITTING = "editing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
