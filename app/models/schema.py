from typing import Dict, List, Optional
from pydantic import BaseModel
from app.models.types import QualityTier

# --- API Models ---


class GenerateRequest(BaseModel):
    """프레젠테이션 생성을 위한 기본 요청 모델"""

    user_request: str
    quality: QualityTier = QualityTier.DEFAULT
    # 스트리밍 전용 옵션 (일반 generate에는 영향 없음)
    ordered: bool = False  # 완료순이 아닌 슬라이드 인덱스 순으로 전송할지 여부
    concurrency: int | None = None  # 동시 작업 수(미지정 시 tier 기본값 사용)


# --- Data Models ---


# 1) 단계 A 결과: 덱 기획
class SlideSpec(BaseModel):
    slide_id: int
    title: str
    key_points: Optional[List[str]] = None  # bullet points
    numbers: Optional[Dict[str, float]] = None  # KPI/지표
    notes: Optional[str] = None
    section: Optional[str] = None


class DeckPlan(BaseModel):
    topic: str
    audience: str
    slides: List[SlideSpec]


# 2) NEW: 후보 템플릿 선택 결과 (단계 A' = select_layout_candidates)
class TemplateCandidate(BaseModel):
    template_name: str
    reason: Optional[str] = None


class SlideCandidates(BaseModel):
    slide_id: int
    candidates: List[TemplateCandidate]


class LayoutSelection(BaseModel):
    items: List[SlideCandidates]


# 3) 단계 B 결과: 최종 HTML
class SlideHTML(BaseModel):
    slide_id: int
    template_name: str
    html: str


# --- API Requests for modular endpoints ---


class PlanRequest(BaseModel):
    """Request to plan a deck without rendering slides."""

    user_request: str
    quality: QualityTier = QualityTier.DEFAULT


class LayoutSelectRequest(BaseModel):
    """Select candidate templates for each slide based on a deck plan."""

    deck_plan: DeckPlan
    quality: QualityTier = QualityTier.DEFAULT


class RenderSlidesRequest(BaseModel):
    """Render a subset or all slides for a given deck plan."""

    deck_plan: DeckPlan
    # If omitted, render all slides in deck_plan.slides
    slides: Optional[List[SlideSpec]] = None
    # Mapping of slide_id to candidate template names
    candidate_map: Optional[Dict[int, List[str]]] = None
    quality: QualityTier = QualityTier.DEFAULT


class PreviewSlideRequest(BaseModel):
    """Render a single slide preview."""

    deck_plan: DeckPlan
    # Provide either a full slide spec or just a slide_id within deck_plan
    slide: Optional[SlideSpec] = None
    slide_id: Optional[int] = None
    # Optional explicit candidate templates; if omitted, selector will pick
    candidate_templates: Optional[List[str]] = None
    quality: QualityTier = QualityTier.DEFAULT
