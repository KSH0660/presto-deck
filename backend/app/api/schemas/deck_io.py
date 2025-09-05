"""
Deck input/output schemas for API requests and responses.

This module contains all the Pydantic schemas for deck-related API endpoints,
separated from the base schemas to follow the recommended structure.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base import BaseResponse, DeckSource, Pagination


# ---------- DECK REQUEST SCHEMAS ----------
class CreateDeckRequest(BaseModel):
    """
    Request to create a new presentation deck.

    Maintains backward compatibility while adding extensible fields
    for enhanced content generation.
    """

    prompt: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Main content prompt describing the deck to generate",
    )

    style_preferences: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional style and design preferences"
    )

    # Extensibility fields (all optional for backward compatibility)
    template_type: Optional[str] = Field(
        default=None,
        description="Template family hint (e.g., 'corporate', 'minimal', 'creative')",
    )

    slide_count: Optional[int] = Field(
        default=None,
        ge=1,
        le=200,
        description="Desired number of slides (AI will use as guidance)",
    )

    sources: Optional[List[DeckSource]] = Field(
        default=None,
        description="Reference materials (URLs, files, text) to inform content",
    )


class UpdateDeckMetadataRequest(BaseModel):
    """Update deck metadata without affecting slides."""

    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    template_type: Optional[str] = Field(None, description="Change template family")


class CancelDeckRequest(BaseModel):
    """Request to cancel ongoing deck generation."""

    reason: Optional[str] = Field(None, description="Optional cancellation reason")


class RegenerateDeckRequest(BaseModel):
    """Request to regenerate deck with new parameters."""

    prompt: Optional[str] = Field(None, description="New prompt (if changing)")
    template_type: Optional[str] = Field(None, description="New template type")
    preserve_slides: Optional[List[str]] = Field(
        None, description="Slide IDs to preserve during regeneration"
    )


# ---------- DECK RESPONSE SCHEMAS ----------
class DeckSummary(BaseModel):
    """Basic deck information for list views and quick references."""

    deck_id: str
    status: str  # Using string instead of enum to avoid API layer depending on domain
    slide_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    title: Optional[str] = Field(None, description="Auto-generated or user-set title")
    template_type: Optional[str] = Field(None, description="Template type used")


class CreateDeckResponse(BaseResponse):
    """Response after creating a new deck."""

    deck_id: str
    status: str
    template_type: Optional[str] = None


class DeckStatusResponse(BaseModel):
    """
    Detailed deck status with optional progress tracking.

    Extended from basic status to include progress indicators
    for better user experience during generation.
    """

    deck_id: str
    status: str
    slide_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Progress tracking extensions (optional for backward compatibility)
    progress: Optional[int] = Field(
        default=None, ge=0, le=100, description="Completion percentage (0-100)"
    )

    current_step: Optional[str] = Field(
        default=None,
        description="Current generation step (e.g., 'planning', 'rendering', 'editing')",
    )

    estimated_completion: Optional[datetime] = Field(
        default=None, description="Estimated completion time (if available)"
    )


class DeckListResponse(BaseModel):
    """Paginated list of decks for dashboard/overview pages."""

    items: List[DeckSummary]
    pagination: Pagination


class DeckDetailsResponse(BaseModel):
    """
    Complete deck information including metadata and configuration.

    Excludes slides (use dedicated slide endpoints for that).
    """

    deck_id: str
    status: str
    slide_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Extended metadata
    title: Optional[str] = None
    description: Optional[str] = None
    template_type: Optional[str] = None
    style_preferences: Optional[Dict[str, Any]] = None
    sources: Optional[List[DeckSource]] = None

    # Generation metadata
    original_prompt: Optional[str] = Field(None, description="Original user prompt")
    generation_config: Optional[Dict[str, Any]] = Field(
        None, description="Configuration used for generation"
    )


class CancelDeckResponse(BaseResponse):
    """Response to deck cancellation request."""

    deck_id: str
    cancelled_at: datetime


# ---------- DECK SHARING & COLLABORATION ----------
class DeckShareRequest(BaseModel):
    """Request to share deck with other users."""

    user_emails: List[str] = Field(..., description="Email addresses to share with")
    permission_level: str = Field(..., description="view|comment|edit")
    message: Optional[str] = Field(None, description="Optional message to recipients")


class DeckShareResponse(BaseModel):
    """Response to deck sharing request."""

    share_id: str
    shared_with: List[str]
    expires_at: Optional[datetime] = None
