"""덱 관련 API DTO"""

from typing import List, Optional, Literal
from pydantic import BaseModel
from app.domain.value_objects.quality import QualityTier


class CreateDeckRequest(BaseModel):
    """덱 생성 요청 DTO"""

    user_prompt: str
    theme: Optional[str] = None
    color_preference: Optional[str] = None
    quality: QualityTier = QualityTier.DEFAULT
    ordered: bool = False
    concurrency: Optional[int] = None


class EditSlideRequest(BaseModel):
    """슬라이드 편집 요청 DTO"""

    edit_prompt: str


class AddSlideRequest(BaseModel):
    """슬라이드 추가 요청 DTO"""

    add_prompt: str


class SlideResponse(BaseModel):
    """슬라이드 응답 DTO"""

    id: int
    title: str
    html_content: Optional[str] = None
    version: int
    status: str


class DeckResponse(BaseModel):
    """덱 응답 DTO"""

    id: str
    topic: str
    audience: str
    theme: Optional[str] = None
    color_preference: Optional[str] = None
    slides: List[SlideResponse]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    version: int


class DeckListResponse(BaseModel):
    """덱 목록 응답 DTO"""

    decks: List[DeckResponse]


class DeleteResponse(BaseModel):
    """삭제 응답 DTO"""

    status: Literal["deleted"]
    id: str
