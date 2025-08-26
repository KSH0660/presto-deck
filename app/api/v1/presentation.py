from typing import Dict, List
from fastapi import APIRouter, HTTPException

# Refactored imports
from app.core import planner, layout_selector, slide_worker
from app.core.concurrency import run_concurrently
from app.core.config import settings
from app.models.schema import (
    SlideHTML,
    GenerateRequest,
    PlanRequest,
    LayoutSelectRequest,
    RenderSlidesRequest,
    PreviewSlideRequest,
)
from app.models.types import QualityTier

router = APIRouter()


@router.post("/generate")
async def generate_presentation(req: GenerateRequest):
    """
    사용자 요청을 받아 프레젠테이션 생성 파이프라인을 비동기적으로 실행합니다.
    서버는 요청의 'quality' 등급에 따라 모델과 동시성을 결정합니다.
    """
    try:
        # 1. 요청 품질 등급에 따라 운영 파라미터 결정
        if req.quality == QualityTier.PREMIUM:
            model = settings.PREMIUM_MODEL
            max_concurrency = settings.PREMIUM_MAX_CONCURRENCY
        elif req.quality == QualityTier.DRAFT:
            model = settings.DRAFT_MODEL
            max_concurrency = settings.DRAFT_MAX_CONCURRENCY
        else:  # DEFAULT
            model = settings.DEFAULT_MODEL
            max_concurrency = settings.DEFAULT_MAX_CONCURRENCY

        # 2. 덱 전체 기획
        deck_plan = await planner.plan_deck(req.user_request, model)

        # 3. 슬라이드별 레이아웃 후보 선택
        selection = await layout_selector.select_layouts(deck_plan, model)

        slide_to_candidates: Dict[int, List[str]] = {}
        for item in selection.items:
            slide_to_candidates[item.slide_id] = [
                c.template_name for c in item.candidates
            ][:3]

        # 4. 템플릿 카탈로그 로드
        template_catalog = layout_selector.load_template_catalog()

        # 5. 각 슬라이드를 비동기 워커로 생성
        tasks = []
        for slide_spec in deck_plan.slides:
            candidate_names = slide_to_candidates.get(slide_spec.slide_id, [])
            task = slide_worker.process_slide(
                slide_spec=slide_spec,
                deck_plan=deck_plan,
                candidate_template_names=candidate_names,
                template_catalog=template_catalog,
                model=model,
            )
            tasks.append(task)

        rendered_slides: List[SlideHTML] = await run_concurrently(
            tasks, max_concurrency=max_concurrency
        )

        # 6. 최종 결과 조합
        plan_dict = deck_plan.model_dump()
        plan_dict["slides"] = [s.model_dump() for s in rendered_slides]

        return plan_dict

    except Exception as e:
        print(f"Error during presentation generation: {e}")
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {e}"
        )


@router.post("/plan")
async def plan_only(req: PlanRequest):
    """Return only the planned deck structure without rendering slides."""
    try:
        if req.quality == QualityTier.PREMIUM:
            model = settings.PREMIUM_MODEL
        elif req.quality == QualityTier.DRAFT:
            model = settings.DRAFT_MODEL
        else:
            model = settings.DEFAULT_MODEL

        deck_plan = await planner.plan_deck(req.user_request, model)
        return deck_plan.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/layouts/select")
async def select_layouts_endpoint(req: LayoutSelectRequest):
    """Select candidate templates for slides given a deck plan."""
    try:
        if req.quality == QualityTier.PREMIUM:
            model = settings.PREMIUM_MODEL
        elif req.quality == QualityTier.DRAFT:
            model = settings.DRAFT_MODEL
        else:
            model = settings.DEFAULT_MODEL

        selection = await layout_selector.select_layouts(req.deck_plan, model)
        return selection.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/slides/render")
async def render_slides(req: RenderSlidesRequest):
    """Render one or more slides for a given deck plan."""
    try:
        if req.quality == QualityTier.PREMIUM:
            model = settings.PREMIUM_MODEL
            max_concurrency = settings.PREMIUM_MAX_CONCURRENCY
        elif req.quality == QualityTier.DRAFT:
            model = settings.DRAFT_MODEL
            max_concurrency = settings.DRAFT_MAX_CONCURRENCY
        else:
            model = settings.DEFAULT_MODEL
            max_concurrency = settings.DEFAULT_MAX_CONCURRENCY

        slides = req.slides or req.deck_plan.slides
        candidate_map = req.candidate_map or {}

        template_catalog = layout_selector.load_template_catalog()
        tasks = []
        for slide_spec in slides:
            candidates = candidate_map.get(slide_spec.slide_id, [])
            tasks.append(
                slide_worker.process_slide(
                    slide_spec=slide_spec,
                    deck_plan=req.deck_plan,
                    candidate_template_names=candidates,
                    template_catalog=template_catalog,
                    model=model,
                )
            )

        rendered_slides = await run_concurrently(tasks, max_concurrency=max_concurrency)
        return {"slides": [s.model_dump() for s in rendered_slides]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preview")
async def preview_slide(req: PreviewSlideRequest):
    """Render a single slide preview. If candidate templates are not provided, pick automatically."""
    try:
        if req.quality == QualityTier.PREMIUM:
            model = settings.PREMIUM_MODEL
        elif req.quality == QualityTier.DRAFT:
            model = settings.DRAFT_MODEL
        else:
            model = settings.DEFAULT_MODEL

        # Determine slide spec
        slide_spec = req.slide
        if slide_spec is None and req.slide_id is not None:
            slide_spec = next(
                (s for s in req.deck_plan.slides if s.slide_id == req.slide_id), None
            )
        if slide_spec is None:
            raise HTTPException(status_code=400, detail="Provide slide or slide_id")

        # Determine candidates
        candidate_templates = req.candidate_templates
        if not candidate_templates:
            selection = await layout_selector.select_layouts(req.deck_plan, model)
            slide_sel = next(
                (i for i in selection.items if i.slide_id == slide_spec.slide_id), None
            )
            candidate_templates = [
                c.template_name for c in (slide_sel.candidates if slide_sel else [])
            ][:3]

        template_catalog = layout_selector.load_template_catalog()
        result: SlideHTML = await slide_worker.process_slide(
            slide_spec=slide_spec,
            deck_plan=req.deck_plan,
            candidate_template_names=candidate_templates or [],
            template_catalog=template_catalog,
            model=model,
        )
        return result.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
