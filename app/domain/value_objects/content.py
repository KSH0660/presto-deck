"""슬라이드 콘텐츠 값 객체"""

from typing import Dict, List, Optional
from pydantic import BaseModel


class SlideContent(BaseModel):
    """슬라이드 콘텐츠 값 객체"""

    title: str
    key_points: Optional[List[str]] = None
    numbers: Optional[Dict[str, float]] = None
    notes: Optional[str] = None
    section: Optional[str] = None

    @property
    def has_key_points(self) -> bool:
        """키 포인트 존재 여부"""
        return self.key_points is not None and len(self.key_points) > 0

    @property
    def has_numbers(self) -> bool:
        """숫자 데이터 존재 여부"""
        return self.numbers is not None and len(self.numbers) > 0

    @property
    def has_notes(self) -> bool:
        """노트 존재 여부"""
        return self.notes is not None and len(self.notes.strip()) > 0

    def __str__(self) -> str:
        return self.title
