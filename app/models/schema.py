from typing import Dict, List, Optional
from pydantic import BaseModel
from app.models.types import QualityTier

# --- API Models ---


class GenerateRequest(BaseModel):
    user_request: str
    quality: QualityTier = QualityTier.DEFAULT


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
