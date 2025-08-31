"""품질 관련 값 객체"""

from enum import Enum
from pydantic import BaseModel


class QualityTier(str, Enum):
    """품질 티어"""

    DRAFT = "draft"
    DEFAULT = "default"
    PREMIUM = "premium"


class GenerationConfig(BaseModel):
    """생성 설정 값 객체"""

    quality: QualityTier = QualityTier.DEFAULT
    ordered: bool = False
    concurrency: int | None = None

    @property
    def is_premium(self) -> bool:
        """프리미엄 품질 여부"""
        return self.quality == QualityTier.PREMIUM

    @property
    def is_draft(self) -> bool:
        """드래프트 품질 여부"""
        return self.quality == QualityTier.DRAFT
