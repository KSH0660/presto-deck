"""덱(프레젠테이션) 도메인 엔티티"""

from typing import List, Optional
from pydantic import BaseModel, Field
from app.domain.entities.slide import Slide
from app.domain.value_objects.deck_metadata import DeckMetadata


class Deck(BaseModel):
    """덱 엔티티 - 프레젠테이션 덱의 핵심 비즈니스 모델"""

    id: str
    metadata: DeckMetadata
    slides: List[Slide] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    version: int = 1

    def add_slide(self, slide: Slide) -> None:
        """슬라이드 추가"""
        self.slides.append(slide)
        self.version += 1

    def remove_slide(self, slide_id: int) -> bool:
        """슬라이드 제거"""
        for i, slide in enumerate(self.slides):
            if slide.id == slide_id:
                self.slides.pop(i)
                self.version += 1
                return True
        return False

    def get_slide(self, slide_id: int) -> Optional[Slide]:
        """특정 슬라이드 조회"""
        for slide in self.slides:
            if slide.id == slide_id:
                return slide
        return None

    def update_slide(self, slide_id: int, updated_slide: Slide) -> bool:
        """슬라이드 업데이트"""
        for i, slide in enumerate(self.slides):
            if slide.id == slide_id:
                self.slides[i] = updated_slide
                self.version += 1
                return True
        return False

    @property
    def slide_count(self) -> int:
        """총 슬라이드 수"""
        return len(self.slides)

    @property
    def is_empty(self) -> bool:
        """빈 덱 여부"""
        return len(self.slides) == 0
