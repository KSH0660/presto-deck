"""기존 템플릿 코드와 연결하는 어댑터"""

from typing import List, Dict
from app.domain.value_objects.content import SlideContent
from app.ports.services.template_service import TemplateService


class LegacyTemplateAdapter(TemplateService):
    """기존 템플릿 코드와 연결하는 임시 어댑터"""

    async def get_template_names(self) -> List[str]:
        """사용 가능한 템플릿 이름 목록 - 기존 코드와 연결 필요"""
        # TODO: 기존 template manager 코드와 연결
        return [
            "title-content",
            "bullet-points",
            "two-column",
            "chart-focus",
            "image-text",
        ]

    async def get_template_summaries(self) -> Dict[str, str]:
        """템플릿 이름과 요약 매핑 - 기존 코드와 연결 필요"""
        return {
            "title-content": "Simple title and content layout",
            "bullet-points": "Perfect for key points and lists",
            "two-column": "Side-by-side content layout",
            "chart-focus": "Optimized for data visualization",
            "image-text": "Image with accompanying text",
        }

    async def select_templates(self, content: SlideContent) -> List[str]:
        """콘텐츠에 적합한 템플릿 선택 - 기존 코드와 연결 필요"""
        # TODO: 기존 template selection 로직과 연결
        if content.has_key_points:
            return ["bullet-points", "title-content"]
        elif content.has_numbers:
            return ["chart-focus", "two-column"]
        else:
            return ["title-content", "two-column"]

    async def validate_template(self, template_name: str) -> bool:
        """템플릿 유효성 검증"""
        available_templates = await self.get_template_names()
        return template_name in available_templates
