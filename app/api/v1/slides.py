# app/api/v1/slides.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.core.infra import state
from app.core.rendering.edit import edit_slide_content
from app.core.rendering.add import add_slide_content
from app.models.schema import (
    SlideEditRequest,
    SlideAddRequest,
    SlideModel,
    DeleteResponse,
)

router = APIRouter()


@router.post(
    "/slides/{slide_id}/edit",
    response_class=JSONResponse,
    response_model=SlideModel,
)
async def edit_slide(slide_id: int, req: SlideEditRequest) -> JSONResponse:
    """슬라이드 HTML을 편집합니다."""
    slide_to_edit = next((s for s in state.slides_db if s["id"] == slide_id), None)
    if not slide_to_edit:
        raise HTTPException(status_code=404, detail="Slide not found")

    slide_to_edit["status"] = "editing"
    try:
        new_html = await edit_slide_content(
            original_html=slide_to_edit["html_content"], edit_prompt=req.edit_prompt
        )
        slide_to_edit["html_content"] = new_html
        slide_to_edit["version"] = int(slide_to_edit.get("version", 0)) + 1
    finally:
        slide_to_edit["status"] = "complete"

    return JSONResponse(
        content={
            "id": slide_to_edit["id"],
            "title": slide_to_edit.get("title", ""),
            "html_content": slide_to_edit["html_content"],
            "version": slide_to_edit["version"],
            "status": slide_to_edit["status"],
        }
    )


@router.post(
    "/slides/add",
    response_class=JSONResponse,
    response_model=SlideModel,
    status_code=201,
)
async def add_slide(req: SlideAddRequest) -> JSONResponse:
    """새 슬라이드를 생성하여 저장합니다."""
    new_content = await add_slide_content(req.add_prompt)
    new_slide = {
        "id": state.get_next_slide_id(),
        "title": new_content["title"],
        "html_content": new_content["html_content"],
        "version": 1,
        "status": "complete",
    }
    state.slides_db.append(new_slide)
    return JSONResponse(content=new_slide, status_code=201)


@router.get("/slides", response_class=JSONResponse, response_model=list[SlideModel])
async def get_slides() -> JSONResponse:
    """현재 저장된 모든 슬라이드를 반환합니다."""
    return JSONResponse(content=state.slides_db)


@router.delete(
    "/slides/{slide_id}/delete",
    response_model=DeleteResponse,
)
async def delete_slide(slide_id: int) -> JSONResponse:
    """슬라이드를 삭제하고 결과 상태를 반환합니다."""
    before = len(state.slides_db)
    state.slides_db = [s for s in state.slides_db if s["id"] != slide_id]
    if len(state.slides_db) == before:
        raise HTTPException(status_code=404, detail="Slide not found")
    return JSONResponse({"status": "deleted", "id": slide_id})
