from datetime import datetime, UTC
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.domain.entities import DeckStatus


# Event Types
EventType = Literal[
    "DeckStarted",
    "PlanUpdated",
    "SlideAdded",
    "SlideUpdated",
    "DeckCompleted",
    "DeckFailed",
    "DeckCancelled",
    "Heartbeat",
]


# Base Event Schema
class Event(BaseModel):
    event_type: EventType
    deck_id: UUID
    version: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: Dict[str, Any] = Field(default_factory=dict)


# API Request/Response Schemas
class DeckCreationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    topic: str = Field(..., min_length=10, max_length=1000)
    audience: Optional[str] = Field(None, max_length=500)
    style: Optional[str] = Field(default="professional", max_length=100)
    slide_count: Optional[int] = Field(default=5, ge=3, le=20)
    language: Optional[str] = Field(default="en", max_length=10)
    include_speaker_notes: bool = Field(default=True)


class SlideResponse(BaseModel):
    id: UUID
    deck_id: UUID
    slide_order: int
    html_content: str
    presenter_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeckResponse(BaseModel):
    id: UUID
    user_id: str
    title: str
    status: DeckStatus
    version: int
    deck_plan: Optional[Dict[str, Any]] = None
    slides: List[SlideResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeckListResponse(BaseModel):
    id: UUID
    title: str
    status: DeckStatus
    slide_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeckCreationResponse(BaseModel):
    deck_id: UUID
    status: DeckStatus
    message: str = "Deck creation started"


class CancellationResponse(BaseModel):
    message: str
    deck_id: UUID
    status: DeckStatus


# WebSocket Message Schemas
class WebSocketMessage(BaseModel):
    type: str
    data: Dict[str, Any] = Field(default_factory=dict)


class SlideUpdateRequest(BaseModel):
    slide_id: UUID
    prompt: str = Field(..., min_length=10, max_length=1000)


class SlideAddRequest(BaseModel):
    position: int = Field(..., ge=1)
    prompt: str = Field(..., min_length=10, max_length=1000)


# Authentication Schemas
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    user_id: Optional[str] = None


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    created_at: datetime
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


# Health Check Schema
class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    services: Dict[str, bool] = Field(default_factory=dict)
    version: str


# Error Schemas
class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ValidationErrorResponse(BaseModel):
    error: str = "validation_error"
    message: str
    details: List[Dict[str, Any]]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
