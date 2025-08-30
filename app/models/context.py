from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel

from app.models.schema import (
    GenerateRequest,
    InitialDeckPlan,
    DeckPlan,
    SlideHTML,
)


class GenerateOptions(BaseModel):
    """슬라이드 생성 실행 옵션(모델, 동시성, 정렬 등)."""

    model: str
    max_concurrency: int
    ordered: bool = False
    heartbeat_interval_sec: int = 15


class PipelineContext(BaseModel):
    """파이프라인 전 단계에서 공유되는 컨텍스트."""

    req: GenerateRequest
    options: GenerateOptions

    # 런타임 리소스/캐시
    template_catalog: Dict[str, str] = {}

    # 단계별 산출물
    initial_deck_plan: Optional[InitialDeckPlan] = None
    deck_plan: Optional[DeckPlan] = None
    slides: List[SlideHTML] = []

    # 취소 시그널(옵션)
    cancelled: bool = False
