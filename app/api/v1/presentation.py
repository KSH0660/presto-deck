from typing import List
from fastapi import APIRouter, HTTPException

# Refactored imports
from app.core import planner, layout_selector, slide_worker
from app.core.concurrency import run_concurrently
from app.core.config import settings
from app.core.template_manager import get_template_html_catalog
from app.models.schema import (
    SlideHTML,
    GenerateRequest,
)
from app.models.types import QualityTier

router = APIRouter()


@router.post("/generate")
async def generate_presentation(req: GenerateRequest):
    """
    사용자 요청을 받아 프레젠테이션 생성 파이프라인을 비동기적으로 실행합니다.
    """
    try:
        if req.config.quality == QualityTier.PREMIUM:
            model = settings.PREMIUM_MODEL
            max_concurrency = settings.PREMIUM_MAX_CONCURRENCY
        elif req.config.quality == QualityTier.DRAFT:
            model = settings.DRAFT_MODEL
            max_concurrency = settings.DRAFT_MAX_CONCURRENCY
        else:  # DEFAULT
            model = settings.DEFAULT_MODEL
            max_concurrency = settings.DEFAULT_MAX_CONCURRENCY

        deck_plan = await planner.plan_deck(req.user_prompt, model)

        deck_plan = await layout_selector.run_layout_selection_for_deck(
            deck_plan=deck_plan, user_request=req.user_prompt, model=model
        )

        template_catalog = get_template_html_catalog()

        tasks = []
        for slide_spec in deck_plan.slides:
            task = slide_worker.process_slide(
                slide_spec=slide_spec,
                deck_plan=deck_plan,
                candidate_template_names=slide_spec.layout_candidates or [],
                template_catalog=template_catalog,
                model=model,
            )
            tasks.append(task)

        rendered_slides: List[SlideHTML] = await run_concurrently(
            tasks, max_concurrency=max_concurrency
        )

        plan_dict = deck_plan.model_dump()
        rendered_map = {s.slide_id: s for s in rendered_slides}

        for slide_spec in plan_dict["slides"]:
            rendered_slide = rendered_map.get(slide_spec["slide_id"])
            if rendered_slide:
                slide_spec["html"] = rendered_slide.html
                slide_spec["template_name"] = rendered_slide.template_name

        return plan_dict

    except Exception as e:
        print(f"Error during presentation generation: {e}")
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {e}"
        )
