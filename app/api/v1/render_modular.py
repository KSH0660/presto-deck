from typing import List, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.models.schema import DeckPlan, SlideSpec, SlideHTML, GenerateRequest
from app.core.rendering.slide_worker import process_slide
from app.core.templates.template_manager import get_template_html_catalog
from app.core.infra.config import settings
from app.models.types import QualityTier
from app.core.infra import state

router = APIRouter()


def _resolve_model(q: QualityTier) -> str:
    if q == QualityTier.PREMIUM:
        return settings.PREMIUM_MODEL
    if q == QualityTier.DRAFT:
        return settings.DRAFT_MODEL
    return settings.DEFAULT_MODEL


class RenderRequest(GenerateRequest):
    deck_plan: DeckPlan
    slides: Optional[List[SlideSpec]] = None  # subset; default all


@router.post("/slides/render")
async def render_slides(req: RenderRequest) -> JSONResponse:
    """Render slides from a confirmed DeckPlan (optionally a subset)."""
    model = _resolve_model(req.config.quality)
    catalog = get_template_html_catalog()
    targets: List[SlideSpec] = req.slides or req.deck_plan.slides

    rendered: List[SlideHTML] = []
    for spec in targets:
        html = await process_slide(
            slide_spec=spec,
            deck_plan=req.deck_plan,
            req=req,
            template_catalog=catalog,
            model=model,
        )
        rendered.append(html)
        # Persist to in-memory DB so edit/delete endpoints and export work.
        state.slides_db.append(
            {
                "id": spec.slide_id,
                "title": spec.title,
                "html_content": html.html,
                "version": 1,
                "status": "complete",
            }
        )

    # Reset ID counter to next available
    try:
        if state.slides_db:
            max_id = max(s.get("id", 0) for s in state.slides_db)
            state.reset_slide_ids(max_id + 1)
    except Exception:
        pass

    return JSONResponse({"slides": [s.model_dump() for s in rendered]})
