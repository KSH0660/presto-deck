"""기존 LLM 코드와 연결하는 어댑터"""

from typing import List, AsyncIterator
from app.domain.entities.slide import Slide
from app.domain.value_objects.deck_metadata import DeckMetadata
from app.domain.value_objects.content import SlideContent
from app.domain.value_objects.quality import GenerationConfig
from app.ports.services.llm_service import LLMService


class LegacyLLMAdapter(LLMService):
    """기존 LLM 코드와 연결하는 임시 어댑터"""

    async def plan_deck(
        self, user_prompt: str, config: GenerationConfig
    ) -> DeckMetadata:
        """덱 계획 수립 - 기존 코드와 연결 필요"""
        # TODO: 기존 planning 코드와 연결
        return DeckMetadata(
            topic=f"Topic from: {user_prompt[:50]}...", audience="General audience"
        )

    async def generate_slides(
        self, metadata: DeckMetadata, config: GenerationConfig
    ) -> AsyncIterator[Slide]:
        """슬라이드 생성 - 기존 코드와 연결 필요"""
        # TODO: 기존 slide generation 코드와 연결
        for i in range(3):  # 임시로 3개 슬라이드 생성
            content = SlideContent(
                title=f"Slide {i+1}: {metadata.topic}",
                key_points=[f"Point {j+1}" for j in range(3)],
            )
            slide = Slide(id=i + 1, content=content)
            yield slide

    async def render_slide(
        self, slide: Slide, template_names: List[str], config: GenerationConfig
    ) -> Slide:
        """슬라이드 렌더링 - 기존 코드와 연결 필요"""
        # TODO: 기존 rendering 코드와 연결
        template_name = template_names[0] if template_names else "default"
        html_content = f"""
        <div class="slide">
            <h1>{slide.content.title}</h1>
            <ul>
                {chr(10).join(f'<li>{point}</li>' for point in slide.content.key_points or [])}
            </ul>
        </div>
        """
        slide.render_with_template(template_name, html_content)
        return slide

    async def edit_slide(
        self, slide: Slide, edit_prompt: str, config: GenerationConfig
    ) -> Slide:
        """슬라이드 편집 - 기존 코드와 연결 필요"""
        # TODO: 기존 editing 코드와 연결
        new_content = SlideContent(
            title=f"{slide.content.title} (edited)",
            key_points=slide.content.key_points,
            notes=f"Edited with: {edit_prompt}",
        )
        slide.update_content(new_content)
        return slide
