"""LLM 서비스 포트 인터페이스"""

from abc import ABC, abstractmethod
from typing import List, AsyncIterator
from app.domain.entities.slide import Slide
from app.domain.value_objects.deck_metadata import DeckMetadata
from app.domain.value_objects.quality import GenerationConfig


class LLMService(ABC):
    """LLM 서비스 인터페이스"""

    @abstractmethod
    async def plan_deck(
        self, user_prompt: str, config: GenerationConfig
    ) -> DeckMetadata:
        """덱 계획 수립"""
        pass

    @abstractmethod
    async def generate_slides(
        self, metadata: DeckMetadata, config: GenerationConfig
    ) -> AsyncIterator[Slide]:
        """슬라이드 생성"""
        pass

    @abstractmethod
    async def render_slide(
        self, slide: Slide, template_names: List[str], config: GenerationConfig
    ) -> Slide:
        """슬라이드 렌더링"""
        pass

    @abstractmethod
    async def edit_slide(
        self, slide: Slide, edit_prompt: str, config: GenerationConfig
    ) -> Slide:
        """슬라이드 편집"""
        pass
