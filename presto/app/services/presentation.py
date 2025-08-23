import json
import asyncio
from typing import AsyncGenerator

from presto.app.models.presentation import (
    PresentationRequest,
    PresentationOutline,
    SlideContent,
)
from presto.app.core.llm_openai import generate_content_openai
from presto.app.services.template import TemplateService

class PresentationService:
    def __init__(self, template_service: TemplateService):
        self.template_service = template_service

    async def _generate_outline(self, request: PresentationRequest, available_layouts: list[str]) -> PresentationOutline:
        outline_prompt_template = self.template_service.get_prompt_template("outline_prompt.txt")
        outline_prompt = outline_prompt_template.render(
            topic=request.topic,
            slide_count=request.slide_count,
            layouts=available_layouts
        )
        return await generate_content_openai(
            outline_prompt, model=request.model, response_model=PresentationOutline
        )

    async def _generate_slide_content(self, request: PresentationRequest, plan: dict, generated_slides_history: list, slide_outline: dict) -> SlideContent:
        content_prompt_template = self.template_service.get_prompt_template("content_prompt.txt")
        content_prompt = content_prompt_template.render(
            topic=request.topic,
            plan=plan,
            history=generated_slides_history,
            current_slide=slide_outline
        )
        return await generate_content_openai(
            content_prompt, model=request.model, response_model=SlideContent
        )

    def _normalize_content(self, content: any) -> list[str]:
        # content 정규화: str(JSON)로 오는 경우 방어적으로 처리
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                content = [content]

        # 리스트 보장 + 항목을 문자열화(혹시 dict 등 섞여온 경우 대비)
        if not isinstance(content, list):
            content = [str(content)]
        else:
            content = [str(x) for x in content]
        return content

    async def generate_slides_stream(self, request: PresentationRequest) -> AsyncGenerator[str, None]:
        """A generator function that yields presentation slides one by one."""
        try:
            # 1. Get available layouts
            available_layouts = self.template_service.get_available_layouts(request.theme)
            if not available_layouts:
                raise ValueError(f"Theme '{request.theme}' not found.")

            # 2. Generate the high-level outline
            outline = await self._generate_outline(request, available_layouts)
            plan = outline.model_dump()
            slides_outline = outline.slides

            # Yield the initial plan as the first event in the stream
            initial_event = {"type": "plan", "data": plan}
            yield f"data: {json.dumps(initial_event)}\n\n"

            # 3. Sequentially generate content for each slide and yield it
            generated_slides_history = []
            for i, slide_outline in enumerate(slides_outline):
                slide_outline_dict = slide_outline.model_dump()
                slide_content = await self._generate_slide_content(request, plan, generated_slides_history, slide_outline_dict)
                
                content_list = self._normalize_content(slide_content.content)

                full_slide_data = {
                    "title": slide_outline.title,
                    "content": content_list,
                }
                generated_slides_history.append(full_slide_data)

                rendered_html = self.template_service.render_slide_html(
                    request.theme, 
                    getattr(slide_outline, "layout", "list"), 
                    full_slide_data
                )

                # Yield the slide data
                slide_event = {"type": "slide", "data": {"html": rendered_html, "slide_number": i + 1}}
                yield f"data: {json.dumps(slide_event)}\n\n"
                await asyncio.sleep(0.1) # Small delay for stream flushing

        except Exception as e:
            # Catch any other unexpected errors
            error_event = {"type": "error", "data": {"message": f"An unexpected error occurred: {str(e)}"}}
            yield f"data: {json.dumps(error_event)}\n\n"
