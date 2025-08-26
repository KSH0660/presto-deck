# app/models/types.py

from enum import Enum


class QualityTier(str, Enum):
    """요청의 품질 등급을 나타내는 Enum"""

    DRAFT = "draft"
    DEFAULT = "default"
    PREMIUM = "premium"
