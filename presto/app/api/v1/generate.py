import os
import json
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from presto.app.models.presentation import (
    PresentationRequest, 
    PresentationOutline,
    SlideContent,
)
from presto.app.core.llm_openai import generate_content_openai

router = APIRouter()

# --- Setup ---
PROMPT_DIR = os.path.join("presto", "prompts")
TEMPLATE_DIR = os.path.join("presto", "templates")

# Jinja2 for HTML templating
template_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

# Jinja2 for prompt templating
prompt_env = Environment(loader=FileSystemLoader(PROMPT_DIR))

def get_available_layouts(theme: str) -> list[str]:
    """Scans the file system to get available layout names for a given theme."""
    try:
        theme_dir = os.path.join(TEMPLATE_DIR, theme)
        if not os.path.isdir(theme_dir):
            return []
        return [f.replace(".html", "") for f in os.listdir(theme_dir) if f.endswith(".html")]
    except Exception:
        return []

async def presentation_generator(request: PresentationRequest):
    """A generator function that yields presentation slides one by one."""
    try:
        # 1. Get available layouts and load prompts
        available_layouts = get_available_layouts(request.theme)
        if not available_layouts:
            raise HTTPException(status_code=404, detail=f"Theme '{request.theme}' not found.")

        outline_prompt_template = prompt_env.get_template("outline_prompt.txt")
        content_prompt_template = prompt_env.get_template("content_prompt.txt")

        # 2. Generate the high-level outline
        outline_prompt = outline_prompt_template.render(
            topic=request.topic,
            slide_count=request.slide_count,
            layouts=available_layouts
        )
        outline: PresentationOutline = await generate_content_openai(
            outline_prompt, model=request.model, response_model=PresentationOutline
        )
        plan = outline.model_dump()
        slides_outline = outline.slides

        # Yield the initial plan as the first event in the stream
        initial_event = {"type": "plan", "data": plan}
        yield f"data: {json.dumps(initial_event)}\n\n"

        # 3. Sequentially generate content for each slide and yield it
        generated_slides_history = []
        for i, slide_outline in enumerate(slides_outline):
            # Generate content for the current slide
            content_prompt = content_prompt_template.render(
                topic=request.topic,
                plan=plan,
                history=generated_slides_history,
                current_slide=slide_outline.model_dump()
            )
            slide_content: SlideContent = await generate_content_openai(
                content_prompt, model=request.model, response_model=SlideContent
            )
            
            # 1) content 정규화: str(JSON)로 오는 경우 방어적으로 처리
            content_list = slide_content.content
            if isinstance(content_list, str):
                try:
                    content_list = json.loads(content_list)
                except json.JSONDecodeError:
                    content_list = [content_list]

            # 리스트 보장 + 항목을 문자열화(혹시 dict 등 섞여온 경우 대비)
            if not isinstance(content_list, list):
                content_list = [str(content_list)]
            else:
                content_list = [str(x) for x in content_list]

            # 2) 템플릿이 기대하는 형태로 "평탄화"
            full_slide_data = {
                "title": slide_outline.title,  # {{ title }}
                "content": content_list,       # {% for item in content %}의 대상
            }
            generated_slides_history.append(full_slide_data)

            # Render the HTML for the slide
            layout = getattr(slide_outline, "layout", "list")
            template_name = f"{request.theme}/{layout}.html"
            
            try:
                template = template_env.get_template(template_name)
                rendered_html = template.render(**full_slide_data)
            except TemplateNotFound:
                rendered_html = f"<div><h2>Error</h2><p>Layout '{layout}' not found.</p></div>"

            # Yield the slide data
            slide_event = {"type": "slide", "data": {"html": rendered_html, "slide_number": i + 1}}
            yield f"data: {json.dumps(slide_event)}\n\n"
            await asyncio.sleep(0.1) # Small delay for stream flushing

    except Exception as e:
        # Catch any other unexpected errors
        error_event = {"type": "error", "data": {"message": f"An unexpected error occurred: {str(e)}"}}
        yield f"data: {json.dumps(error_event)}\n\n"

@router.post("/generate")
async def generate_presentation_stream(request: PresentationRequest):
    """
    Creates a new presentation by streaming the results slide by slide.
    Uses Server-Sent Events (SSE).
    """
    return StreamingResponse(presentation_generator(request), media_type="text/event-stream")
