"""
DEPRECATED: This file has been split into feature-based modules.

Use the new modular structure:
- app.api.schemas.base: Common types, enums, pagination
- app.api.schemas.deck: Deck operations
- app.api.schemas.slide: Slide operations
- app.api.schemas.websocket: WebSocket and events

For backward compatibility, import from app.api.schemas directly:
    from app.api.schemas import CreateDeckRequest, SlideOut, DeckEventOut

This file will be removed in a future version.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, HttpUrl, ConfigDict
from typing_extensions import Literal


# ---------- ENUMS ----------
class DeckStatus(str, Enum):
    pending = "pending"
    planning = "planning"
    rendering = "rendering"
    editing = "editing"
    completed = "completed"
    failed = "failed"


class EventType(str, Enum):
    DeckStarted = "DeckStarted"
    SlideAdded = "SlideAdded"
    SlideEdited = "SlideEdited"
    SlideReordered = "SlideReordered"
    SlideDeleted = "SlideDeleted"
    SlideRestored = "SlideRestored"
    DeckCompleted = "DeckCompleted"
    Error = "Error"


# ---------- SHARED ----------
class Pagination(BaseModel):
    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)


# ---------- SOURCES (선택 입력) ----------
class SourceUrl(BaseModel):
    kind: Literal["url"] = "url"
    url: HttpUrl
    title: Optional[str] = None
    notes: Optional[str] = None


class SourceFile(BaseModel):
    kind: Literal["file"] = "file"
    file_id: str  # 업로드된 파일 식별자
    filename: Optional[str] = None
    mimetype: Optional[str] = None


class SourceText(BaseModel):
    kind: Literal["text"] = "text"
    text: str = Field(..., min_length=1, max_length=200_000)
    title: Optional[str] = None


DeckSource = Union[SourceUrl, SourceFile, SourceText]


# ---------- DECK ----------
class CreateDeckRequest(BaseModel):
    """
    기존 필드는 유지(하위호환). 선택 필드만 추가.
    """

    prompt: str = Field(
        ..., min_length=10, max_length=5000, description="Deck content prompt"
    )
    style_preferences: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional style preferences"
    )
    template_type: Optional[str] = Field(
        default=None, description="Template family (e.g., 'corporate', 'minimal')"
    )
    slide_count: Optional[int] = Field(
        default=None, ge=1, le=200, description="Desired slide count (hint)"
    )
    sources: Optional[List[DeckSource]] = Field(
        default=None, description="Optional reference materials"
    )


class DeckSummary(BaseModel):
    deck_id: str
    status: DeckStatus
    slide_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class CreateDeckResponse(BaseModel):
    deck_id: str
    status: DeckStatus
    message: Optional[str] = None


class DeckStatusResponse(BaseModel):
    """
    기존 Response를 확장: progress/step 추가(선택).
    """

    deck_id: str
    status: DeckStatus
    slide_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 확장 포인트 (없어도 동작)
    progress: Optional[int] = Field(default=None, ge=0, le=100)
    current_step: Optional[str] = Field(
        default=None, description="planning|rendering|editing …"
    )


# ---------- SLIDE (출력/편집용) ----------
class SlideOut(BaseModel):
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
    items: List[SlideOut]
    pagination: Pagination


class InsertSlideRequest(BaseModel):
    """
    새 슬라이드 삽입: 위치 지정 두 방식 중 하나만 사용
    """

    after_slide_id: Optional[str] = Field(
        default=None, description="Insert after this slide"
    )
    position: Optional[int] = Field(
        default=None, ge=1, description="1-based order (server will renumber)"
    )
    seed_outline: Optional[str] = Field(
        default=None, description="Optional seed content"
    )
    template_type: Optional[str] = None


class PatchSlideRequest(BaseModel):
    """
    부분 편집(전체 스냅샷 교체해도 OK). reason은 버전 사유 기록용.
    """

    title: Optional[str] = None
    content_outline: Optional[str] = None
    html_content: Optional[str] = None
    presenter_notes: Optional[str] = None
    template_type: Optional[str] = None
    reason: Optional[str] = Field(
        default="user_edit",
        description="user_edit|ai_edit|reorder|insert|delete|revert",
    )


class ReorderSlidesItem(BaseModel):
    slide_id: str
    order: int


class ReorderSlidesRequest(BaseModel):
    orders: List[ReorderSlidesItem]


class DeleteSlideResponse(BaseModel):
    slide_id: str
    soft_deleted: bool = True


# ---------- VERSIONS ----------
class SlideVersionOut(BaseModel):
    id: str
    slide_id: str
    deck_id: str
    version_no: int
    reason: str
    snapshot: Dict[str, Any]  # title, outline, html, notes, template_type, order ...
    created_at: datetime
    created_by: Optional[str] = None


class SlideVersionListResponse(BaseModel):
    items: List[SlideVersionOut]
    pagination: Pagination


class RevertSlideRequest(BaseModel):
    to_version: int


# ---------- EVENTS & STREAM ----------
class DeckEventOut(BaseModel):
    id: str
    deck_id: str
    event_type: EventType
    event_data: Dict[str, Any]
    created_at: datetime
