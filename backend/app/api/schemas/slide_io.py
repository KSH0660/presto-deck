"""
Slide input/output schemas for API requests and responses.

This module contains all the Pydantic schemas for slide-related API endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .base import BaseResponse


# ---------- SLIDE REQUEST SCHEMAS ----------
class CreateSlideRequest(BaseModel):
    """Request to create a new slide in a deck."""

    title: str = Field(..., min_length=1, max_length=200, description="Slide title")
    content_outline: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Content outline or bullet points",
    )
    presenter_notes: Optional[str] = Field(
        default="", max_length=5000, description="Speaker notes for the slide"
    )
    template_filename: Optional[str] = Field(
        default=None, description="Specific template file to use"
    )
    position: Optional[int] = Field(
        default=None, ge=1, description="Position to insert slide (1-based)"
    )


class UpdateSlideRequest(BaseModel):
    """Request to update an existing slide."""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content_outline: Optional[str] = Field(None, min_length=1, max_length=2000)
    html_content: Optional[str] = Field(None, description="Generated HTML content")
    presenter_notes: Optional[str] = Field(None, max_length=5000)
    template_filename: Optional[str] = Field(None, description="Change template")


class ReorderSlidesRequest(BaseModel):
    """Request to reorder slides within a deck."""

    slide_order: List[str] = Field(
        ..., min_items=1, description="List of slide IDs in desired order"
    )


class GenerateSlideContentRequest(BaseModel):
    """Request to regenerate content for a specific slide."""

    regeneration_prompt: Optional[str] = Field(
        None, description="Additional instructions for content generation"
    )
    preserve_outline: bool = Field(
        True, description="Whether to preserve the current outline structure"
    )


# ---------- SLIDE RESPONSE SCHEMAS ----------
class SlideSummary(BaseModel):
    """Basic slide information for list views."""

    slide_id: str
    deck_id: str
    order: int
    title: str
    is_complete: bool = Field(description="Whether slide has generated content")
    template_filename: str
    created_at: datetime
    updated_at: Optional[datetime] = None


class SlideDetails(BaseModel):
    """Complete slide information including content."""

    slide_id: str
    deck_id: str
    order: int
    title: str
    content_outline: str
    html_content: Optional[str] = None
    presenter_notes: str
    template_filename: str
    is_complete: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Content metadata
    content_summary: Optional[str] = Field(
        None, description="Brief summary of slide content"
    )
    word_count: Optional[int] = Field(None, description="Approximate word count")


class CreateSlideResponse(BaseResponse):
    """Response after creating a new slide."""

    slide_id: str
    deck_id: str
    order: int
    title: str


class UpdateSlideResponse(BaseResponse):
    """Response after updating a slide."""

    slide_id: str
    updated_fields: List[str] = Field(description="List of fields that were updated")


class SlideListResponse(BaseModel):
    """List of slides in a deck."""

    deck_id: str
    slides: List[SlideSummary]
    total_slides: int


class ReorderSlidesResponse(BaseResponse):
    """Response after reordering slides."""

    deck_id: str
    slides: List[SlideSummary] = Field(description="Slides in new order")


class DeleteSlideResponse(BaseResponse):
    """Response after deleting a slide."""

    slide_id: str
    deck_id: str
    deleted_at: datetime


# ---------- SLIDE CONTENT & GENERATION ----------
class SlideContentResponse(BaseModel):
    """Response containing slide content for rendering."""

    slide_id: str
    html_content: str
    presenter_notes: str
    template_filename: str
    generated_at: datetime


class GenerateContentResponse(BaseResponse):
    """Response after requesting content generation."""

    slide_id: str
    generation_job_id: str = Field(description="Background job ID for tracking")
    estimated_completion: Optional[datetime] = None


# ---------- SLIDE VERSIONS ----------
class SlideVersion(BaseModel):
    """Information about a slide content version."""

    version_id: str
    slide_id: str
    version_number: int
    html_content: str
    presenter_notes: str
    created_at: datetime
    created_reason: str = Field(description="Reason for creating this version")
    is_current: bool = Field(description="Whether this is the active version")


class SlideVersionListResponse(BaseModel):
    """List of versions for a slide."""

    slide_id: str
    versions: List[SlideVersion]
    current_version: int


class RestoreSlideVersionRequest(BaseModel):
    """Request to restore a specific slide version."""

    version_id: str = Field(..., description="Version ID to restore")
    reason: Optional[str] = Field(None, description="Reason for restoration")


class RestoreSlideVersionResponse(BaseResponse):
    """Response after restoring a slide version."""

    slide_id: str
    restored_version: int
    new_version_number: int = Field(description="New version number after restoration")
