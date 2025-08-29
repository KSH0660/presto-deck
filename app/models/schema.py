from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field
from app.models.types import QualityTier

# --- API Models ---


class GenerationConfig(BaseModel):
    """생성 과정을 제어하는 내부 설정 모델"""

    quality: QualityTier = QualityTier.DEFAULT
    ordered: bool = False  # 스트리밍 시 순서 보장 여부
    concurrency: int | None = None  # 동시 작업 수


class GenerateRequest(BaseModel):
    """프레젠테이션 생성을 위한 사용자 요청 모델"""

    user_prompt: str
    theme: Optional[str] = None
    color_preference: Optional[str] = None
    config: GenerationConfig = GenerationConfig()


class SlideEditRequest(BaseModel):
    """슬라이드 편집을 위한 사용자 요청 모델"""

    edit_prompt: str


class SlideAddRequest(BaseModel):

    add_prompt: str


# --- Data Models ---


# 덱 기획
class SlideContent(BaseModel):
    """Slide content without layout information."""

    slide_id: int
    title: str
    key_points: Optional[List[str]] = None  # bullet points
    numbers: Optional[Dict[str, float]] = None  # KPI/지표
    notes: Optional[str] = None
    section: Optional[str] = None


class SlideSpec(SlideContent):
    """Slide content with layout candidates."""

    layout_candidates: Optional[List[str]] = None


class InitialDeckPlan(BaseModel):
    """덱 기획 1차 결과(레이아웃 전). 테마/컬러 가이드를 포함."""

    topic: str
    audience: str
    # 덱 전반의 스타일 가이드 (프롬프트 일관성용)
    theme: Optional[str] = None
    color_preference: Optional[str] = None
    slides: List[SlideContent]


class DeckPlan(BaseModel):
    """최종 덱 플랜(레이아웃 후보 포함). 테마/컬러를 유지."""

    topic: str
    audience: str
    theme: Optional[str] = None
    color_preference: Optional[str] = None
    slides: List[SlideSpec]


# 2) 단계 B 결과: 후보 템플릿 선택 결과
class LayoutCandidates(BaseModel):
    """List of candidate template names"""

    layout_candidates: List[str] = Field(
        description="List of candidate template names."
    )


# 3) 단계 B 결과: 최종 HTML
class SlideHTML(BaseModel):
    slide_id: int
    template_name: str
    html: str


class TemplateSummary(BaseModel):
    summary: str = Field(
        description="A one-sentence summary of the template's structure and ideal use case."
    )


# --- Response Models (API) ---


class HealthResponse(BaseModel):
    """헬스 체크 응답 모델"""

    status: Literal["ok"]


class ReadyEnv(BaseModel):
    """레디니스 환경 상태"""

    OPENAI_CONFIGURED: bool


class ReadyResponse(BaseModel):
    """레디니스 체크 응답 모델"""

    status: Literal["ready"]
    templates: int
    env: ReadyEnv


class QualityTierConfig(BaseModel):
    """품질 티어 설정 값"""

    model: Optional[str] = None
    max_concurrency: int


class QualityTiers(BaseModel):
    """세 가지 품질 티어 설정"""

    draft: QualityTierConfig
    default: QualityTierConfig
    premium: QualityTierConfig


class MetaResponse(BaseModel):
    """메타 정보 응답"""

    service: Literal["presto-api"]
    version: str
    quality_tiers: QualityTiers
    template_count: int


class TemplatesResponse(BaseModel):
    """템플릿 목록 응답"""

    templates: List[str]


class SlideModel(BaseModel):
    """단일 슬라이드 스키마"""

    id: int
    title: str
    html_content: str
    version: int
    status: str


class DeleteResponse(BaseModel):
    """삭제 결과 응답"""

    status: Literal["deleted"]
    id: int
