"""템플릿 서비스 포트 인터페이스"""

from abc import ABC, abstractmethod
from typing import List, Dict
from app.domain.value_objects.content import SlideContent


class TemplateService(ABC):
    """템플릿 서비스 인터페이스"""

    @abstractmethod
    async def get_template_names(self) -> List[str]:
        """사용 가능한 템플릿 이름 목록"""
        pass

    @abstractmethod
    async def get_template_summaries(self) -> Dict[str, str]:
        """템플릿 이름과 요약 매핑"""
        pass

    @abstractmethod
    async def select_templates(self, content: SlideContent) -> List[str]:
        """콘텐츠에 적합한 템플릿 선택"""
        pass

    @abstractmethod
    async def validate_template(self, template_name: str) -> bool:
        """템플릿 유효성 검증"""
        pass
