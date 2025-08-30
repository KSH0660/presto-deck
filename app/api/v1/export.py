# app/api/v1/export.py
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.core.infra import state

router = APIRouter()


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
