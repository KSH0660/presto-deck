"""
Request/Response schemas for deck operations.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class CreateDeckRequest(BaseModel):
    prompt: str = Field(
        ..., min_length=10, max_length=5000, description="Deck content prompt"
    )
    style_preferences: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional style preferences"
    )


class CreateDeckResponse(BaseModel):
    deck_id: str
    status: str
    message: str


class DeckStatusResponse(BaseModel):
    deck_id: str
    status: str
    slide_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
