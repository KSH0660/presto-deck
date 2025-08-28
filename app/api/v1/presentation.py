# app/api/v1/presentation.py
import logging
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from app.core.streaming import stream_presentation
from app.models.schema import GenerateRequest, SlideEditRequest
from app.core.llm import make_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory store for slides (for MVP)
slides_db = []
next_slide_id = 1

EDIT_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are an expert HTML editor. A user will provide you with a snippet of HTML and a natural language instruction on how to modify it.
            Your task is to return a new, valid HTML snippet that reflects the requested changes.
            ONLY return the HTML code, without any explanations, comments, or markdown formatting.
            Ensure your output is clean and directly usable.""",
        ),
        ("human", "Here is the HTML snippet to edit:\n\n```html\n{original_html}\n```"),
        ("human", "Please make the following change: {edit_prompt}"),
    ]
)


@router.post("/slides/{slide_id}/edit", response_class=HTMLResponse)
async def edit_slide(slide_id: int, req: SlideEditRequest):
    """AI 프롬프트로 슬라이드를 편집하고, 서버의 슬라이드 상태를 HTML로 반환합니다.

    슬라이드가 없을 경우 `client_html_hint`를 기반으로 새로 생성 후 편집합니다.
    반환값은 서버 슬라이드 전체를 단일 HTML로 합친 결과입니다.
    """
    global next_slide_id
    slide_to_edit = next((s for s in slides_db if s["id"] == slide_id), None)

    # 슬라이드가 없으면 생성(초기 HTML 힌트가 있으면 사용)
    if slide_to_edit is None:
        initial_html = req.client_html_hint or ""
        new_title = f"Slide {slide_id}"
        slide_to_edit = {
            "id": slide_id,
            "title": new_title,
            "html_content": initial_html,
            "version": 0,
        }
        slides_db.append(slide_to_edit)
        # next_slide_id는 최대치 기준으로 보정
        next_slide_id = max(next_slide_id, slide_id + 1)

    # AI 편집 체인 실행
    llm = make_llm()
    chain = EDIT_PROMPT_TEMPLATE | llm | StrOutputParser()

    new_html = await chain.ainvoke(
        {
            "original_html": slide_to_edit["html_content"],
            "edit_prompt": req.edit_prompt,
        }
    )

    slide_to_edit["html_content"] = new_html
    slide_to_edit["version"] += 1

    # 서버 보유 슬라이드 전체를 HTML로 렌더링하여 반환
    if not slides_db:
        return HTMLResponse(
            content="<div>No slides yet. Generate a presentation to get started!</div>"
        )
    html_content = ""
    for slide in slides_db:
        html_content += (
            f'<div id="slide-{slide["id"]}"><h3>{slide["title"]}</h3>'
            f'<div>{slide["html_content"]}</div></div>'
        )
    return HTMLResponse(content=html_content)


@router.post("/generate")
async def generate_presentation(req: GenerateRequest):
    """프레젠테이션을 생성하고 SSE로 실시간 스트림합니다."""

    async def event_generator():
        try:
            async for event_data in stream_presentation(req):
                yield event_data.encode("utf-8")
        except Exception as e:
            logger.error("Client-side error or cancellation: %s", e, exc_info=True)
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/slides/{slide_id}/delete")
async def delete_slide(slide_id: int):
    """슬라이드를 삭제하고 결과 상태를 반환합니다."""
    global slides_db
    before = len(slides_db)
    slides_db = [s for s in slides_db if s["id"] != slide_id]
    if len(slides_db) == before:
        raise HTTPException(status_code=404, detail="Slide not found")
    return JSONResponse({"status": "deleted", "id": slide_id})


@router.get("/progress", response_class=StreamingResponse)
async def get_progress():
    """SSE로 진행 상황을 순차적으로 전송합니다."""

    async def progress_generator():
        steps = ["Planning", "Selecting Templates", "Rendering Slides", "Complete"]
        for step in steps:
            yield f"event: step\ndata: {step}\n\n"
            await asyncio.sleep(1)  # Simulate work

    return StreamingResponse(progress_generator(), media_type="text/event-stream")


@router.get("/export/html", response_class=HTMLResponse)
async def export_html():
    """모든 슬라이드를 하나의 HTML 문서로 내보냅니다."""
    if not slides_db:
        return "<div>No slides to export.</div>"

    full_html = "<html><head><title>Presentation</title></head><body>"
    for slide in slides_db:
        full_html += f'<div><h3>{slide["title"]}</h3>{slide["html_content"]}</div><hr>'
    full_html += "</body></html>"

    return full_html
