"""
Slide-related schemas for API requests and responses.
Handles individual slide operations, versioning, and batch operations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict

from .base import BaseResponse, Pagination


# ---------- SLIDE OUTPUT SCHEMAS ----------
class SlideOut(BaseModel):
    """
    Slide data for API responses.

    Represents current state of a slide with all its content.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    deck_id: str
    order: int
    title: str
    content_outline: str
    html_content: Optional[str] = None
    presenter_notes: Optional[str] = None
    template_type: str
    created_at: datetime
    updated_at: Optional[datetime] = None


class SlideListResponse(BaseModel):
    """Paginated list of slides for a deck."""

    items: List[SlideOut]
    pagination: Pagination


# ---------- SLIDE MODIFICATION SCHEMAS ----------
class PatchSlideRequest(BaseModel):
    """
    Partial slide update request.

    All fields optional for partial updates. Creates version snapshot
    automatically before applying changes.
    """

    title: Optional[str] = Field(None, max_length=200)
    content_outline: Optional[str] = Field(None, max_length=5000)
    html_content: Optional[str] = Field(None, max_length=100_000)
    presenter_notes: Optional[str] = Field(None, max_length=10_000)
    template_type: Optional[str] = Field(None, description="Change slide template")

    reason: Optional[str] = Field(
        default="user_edit",
        description="Reason for change: user_edit|ai_edit|reorder|insert|delete|revert",
    )


class InsertSlideRequest(BaseModel):
    """
    Request to insert a new slide into the deck.

    Supports insertion after a specific slide or at a specific position.
    Position-based insertion will renumber subsequent slides.
    """

    # Position specification (use one of these)
    after_slide_id: Optional[str] = Field(
        None, description="Insert after this slide ID"
    )
    position: Optional[int] = Field(
        None, ge=1, description="1-based position (will renumber subsequent slides)"
    )

    # Content initialization
    seed_outline: Optional[str] = Field(
        None, max_length=1000, description="Optional initial content outline"
    )
    template_type: Optional[str] = Field(None, description="Template for new slide")

    # AI generation options
    generate_content: Optional[bool] = Field(
        False, description="Whether to auto-generate content using AI"
    )
    content_prompt: Optional[str] = Field(
        None, max_length=500, description="Prompt for AI content generation"
    )


class BulkSlideUpdateRequest(BaseModel):
    """Update multiple slides in a single operation."""

    updates: List[Dict[str, Any]] = Field(
        ..., description="List of slide updates with slide_id and fields to update"
    )
    reason: str = Field(default="bulk_edit", description="Reason for bulk update")


# ---------- SLIDE ORDERING SCHEMAS ----------
class ReorderSlidesItem(BaseModel):
    """Single slide reordering instruction."""

    slide_id: str
    order: int = Field(..., ge=1)


class ReorderSlidesRequest(BaseModel):
    """
    Request to reorder slides in a deck.

    Provides list of slide_id -> new_order mappings.
    All slides must be included for consistency.
    """

    orders: List[ReorderSlidesItem] = Field(
        ..., description="Complete slide ordering (all slides must be included)"
    )


class DuplicateSlideRequest(BaseModel):
    """Request to duplicate a slide."""

    after_position: Optional[int] = Field(None, ge=1)
    modify_title: bool = Field(True, description="Add '(Copy)' suffix to title")


# ---------- SLIDE DELETION SCHEMAS ----------
class DeleteSlideResponse(BaseResponse):
    """Response to slide deletion request."""

    slide_id: str
    soft_deleted: bool = Field(True, description="Whether this was a soft delete")
    deleted_at: datetime = Field(default_factory=datetime.utcnow)


class RestoreSlideRequest(BaseModel):
    """Request to restore a soft-deleted slide."""

    restore_position: Optional[int] = Field(
        None, ge=1, description="Position to restore to (default: original position)"
    )


# ---------- SLIDE VERSIONING SCHEMAS ----------
class SlideVersionOut(BaseModel):
    """
    Slide version snapshot data.

    Contains complete slide state at a specific point in time
    for version history and rollback functionality.
    """

    id: str
    slide_id: str
    deck_id: str
    version_no: int
    reason: str
    snapshot: Dict[str, Any]  # Complete slide state
    created_at: datetime
    created_by: Optional[str] = None

    # Change tracking
    change_description: Optional[str] = None
    parent_version: Optional[int] = Field(
        None, description="Parent version for branching scenarios"
    )


class SlideVersionListResponse(BaseModel):
    """Paginated list of slide versions."""

    items: List[SlideVersionOut]
    pagination: Pagination


class RevertSlideRequest(BaseModel):
    """Request to revert slide to a specific version."""

    to_version: int = Field(..., ge=1, description="Version number to revert to")
    reason: Optional[str] = Field("manual_revert", description="Reason for reverting")


class CompareVersionsResponse(BaseModel):
    """Response showing differences between two slide versions."""

    slide_id: str
    version_from: int
    version_to: int
    differences: Dict[str, Any] = Field(
        ..., description="Field-by-field differences between versions"
    )


# ---------- SLIDE TEMPLATE SCHEMAS ----------
class ChangeSlideTemplateRequest(BaseModel):
    """Request to change slide template while preserving content."""

    new_template_type: str
    preserve_styling: bool = Field(
        True, description="Attempt to preserve custom styling"
    )
    regenerate_html: bool = Field(
        True, description="Regenerate HTML content with new template"
    )


class SlideTemplatePreviewResponse(BaseModel):
    """Preview of how slide would look with different template."""

    slide_id: str
    template_type: str
    preview_html: str
    estimated_changes: List[str] = Field(
        ..., description="List of changes that would be made"
    )


# ---------- SLIDE EXPORT SCHEMAS ----------
class ExportSlideRequest(BaseModel):
    """Request to export slide in various formats."""

    format: str = Field(..., description="Export format: html|pdf|png|pptx")
    options: Optional[Dict[str, Any]] = Field(
        None, description="Format-specific export options"
    )


class ExportSlideResponse(BaseModel):
    """Response with exported slide data."""

    slide_id: str
    format: str
    export_url: Optional[str] = Field(None, description="URL to download export")
    inline_data: Optional[str] = Field(None, description="Base64 encoded data")
    expires_at: Optional[datetime] = Field(None, description="Export URL expiration")
