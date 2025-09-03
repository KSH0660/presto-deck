"""
Base schemas and common components used across all API schemas.
Shared enums, pagination, and utility schemas.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field, HttpUrl
from typing_extensions import Literal


# ---------- COMMON ENUMS ----------
class DeckStatus(str, Enum):
    """Status of deck generation process."""

    pending = "pending"
    planning = "planning"
    rendering = "rendering"
    editing = "editing"
    completed = "completed"
    failed = "failed"


class EventType(str, Enum):
    """Types of events that can occur during deck operations."""

    DeckStarted = "DeckStarted"
    SlideAdded = "SlideAdded"
    SlideEdited = "SlideEdited"
    SlideReordered = "SlideReordered"
    SlideDeleted = "SlideDeleted"
    SlideRestored = "SlideRestored"
    DeckCompleted = "DeckCompleted"
    Error = "Error"


# ---------- PAGINATION ----------
class Pagination(BaseModel):
    """Standard pagination metadata for list responses."""

    total: int = Field(..., ge=0, description="Total number of items")
    limit: int = Field(..., ge=1, description="Number of items per page")
    offset: int = Field(..., ge=0, description="Number of items to skip")


# ---------- SOURCE INPUT TYPES ----------
class SourceUrl(BaseModel):
    """URL-based reference source for deck generation."""

    kind: Literal["url"] = "url"
    url: HttpUrl
    title: Optional[str] = Field(None, description="Optional title for the URL")
    notes: Optional[str] = Field(None, description="Optional notes about this source")


class SourceFile(BaseModel):
    """File-based reference source for deck generation."""

    kind: Literal["file"] = "file"
    file_id: str = Field(..., description="Uploaded file identifier")
    filename: Optional[str] = Field(None, description="Original filename")
    mimetype: Optional[str] = Field(None, description="MIME type of the file")


class SourceText(BaseModel):
    """Text-based reference source for deck generation."""

    kind: Literal["text"] = "text"
    text: str = Field(
        ..., min_length=1, max_length=200_000, description="Reference text content"
    )
    title: Optional[str] = Field(None, description="Optional title for this text")


# Union type for all source types
DeckSource = Union[SourceUrl, SourceFile, SourceText]


# ---------- BASE RESPONSE MODELS ----------
class BaseResponse(BaseModel):
    """Base response model with common fields."""

    message: Optional[str] = Field(None, description="Optional response message")


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str = Field(..., description="Error type or code")
    detail: str = Field(..., description="Human-readable error description")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------- API METADATA ----------
class APIVersion(BaseModel):
    """API version information."""

    version: str = Field(..., description="API version string")
    build: Optional[str] = Field(None, description="Build identifier")
    commit: Optional[str] = Field(None, description="Git commit hash")
