"""덱 메타데이터 값 객체"""

from typing import Optional
from pydantic import BaseModel


class DeckMetadata(BaseModel):
    """덱의 메타데이터를 나타내는 값 객체"""

    topic: str
    audience: str
    theme: Optional[str] = None
    color_preference: Optional[str] = None

    def __str__(self) -> str:
        return f"{self.topic} (for {self.audience})"

    @property
    def has_theme(self) -> bool:
        """테마 설정 여부"""
        return self.theme is not None

    @property
    def has_color_preference(self) -> bool:
        """색상 선호도 설정 여부"""
        return self.color_preference is not None
