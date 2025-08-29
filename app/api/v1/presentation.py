# app/api/v1/presentation.py
import logging
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from app.core.streaming import stream_presentation
from app.models.schema import GenerateRequest, SlideEditRequest, SlideAddRequest
from app.core.edit import edit_slide_content
from app.core.add import add_slide_content
from app.core import state

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/slides/{slide_id}/edit", response_class=JSONResponse)
async def edit_slide(slide_id: int, req: SlideEditRequest):
    logger.info(
        f"Editing slide ID: {slide_id} with prompt: '{req.edit_prompt[:50]}...'"
    )
    slide_to_edit = next((s for s in state.slides_db if s["id"] == slide_id), None)

    if not slide_to_edit:
        logger.warning(f"Slide ID: {slide_id} not found in database.")
        raise HTTPException(status_code=404, detail="Slide not found")

    slide_to_edit["status"] = "editing"

    try:
        new_html = await edit_slide_content(
            original_html=slide_to_edit["html_content"],
            edit_prompt=req.edit_prompt,
        )
        slide_to_edit["html_content"] = new_html
        if "version" not in slide_to_edit:
            slide_to_edit["version"] = 0
        slide_to_edit["version"] += 1
    finally:
        slide_to_edit["status"] = "complete"

    logger.info(
        f"Successfully edited slide ID: {slide_id}. New version: {slide_to_edit['version']}"
    )
    return JSONResponse(
        content={
            "id": slide_to_edit["id"],
            "html_content": slide_to_edit["html_content"],
            "version": slide_to_edit["version"],
            "status": slide_to_edit["status"],
        }
    )


@router.post("/slides/add", response_class=JSONResponse, status_code=201)
async def add_slide(req: SlideAddRequest):
    """Generates and adds a new slide to the presentation."""

    new_content = await add_slide_content(req.add_prompt)

    new_slide = {
        "id": state.next_slide_id,
        "title": new_content["title"],
        "html_content": new_content["html_content"],
        "version": 1,
        "status": "complete",
    }

    state.slides_db.append(new_slide)
    state.next_slide_id += 1

    return JSONResponse(content=new_slide, status_code=201)


@router.get("/slides", response_class=JSONResponse)
async def get_slides():
    """Returns the current list of all slides."""
    return JSONResponse(content=state.slides_db)


@router.post("/generate")
async def generate_presentation(req: GenerateRequest) -> StreamingResponse:
    """프레젠테이션을 생성하고 SSE로 실시간 스트림합니다."""
    state.slides_db.clear()
    state.next_slide_id = 1

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
async def delete_slide(slide_id: int) -> JSONResponse:
    """슬라이드를 삭제하고 결과 상태를 반환합니다."""
    before = len(state.slides_db)
    state.slides_db = [s for s in state.slides_db if s["id"] != slide_id]
    if len(state.slides_db) == before:
        raise HTTPException(status_code=404, detail="Slide not found")
    return JSONResponse({"status": "deleted", "id": slide_id})


@router.get("/progress", response_class=StreamingResponse)
async def get_progress() -> StreamingResponse:
    """SSE로 진행 상황을 순차적으로 전송합니다."""

    async def progress_generator():
        steps = ["Planning", "Selecting Templates", "Rendering Slides", "Complete"]
        for step in steps:
            yield f"event: step\ndata: {step}\n\n"
            await asyncio.sleep(1)  # Simulate work

    return StreamingResponse(progress_generator(), media_type="text/event-stream")


@router.get("/export/html", response_class=HTMLResponse)
async def export_html() -> HTMLResponse:
    """모든 슬라이드를 하나의 HTML 문서로 내보냅니다."""
    if not state.slides_db:
        return "<div>No slides to export.</div>"

    full_html = "<html><head><title>Presentation</title></head><body>"
    for slide in state.slides_db:
        full_html += f'<div><h3>{slide["title"]}</h3>{slide["html_content"]}</div><hr>'
    full_html += "</body></html>"

    return full_html
