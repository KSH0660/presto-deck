from typing import Dict, List
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import asyncio
import json

# Refactored imports
from app.core import planner, layout_selector, slide_worker
from app.core.concurrency import run_concurrently
from app.core.config import settings
from app.core.llm import make_llm
from app.core.template_manager import get_template_summaries, get_template_html_catalog
from app.models.schema import (
    SlideHTML,
    GenerateRequest,
    PlanRequest,
    RenderSlidesRequest,
    PreviewSlideRequest,
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


@router.post("/plan")
async def plan_only(req: PlanRequest):
    """Return only the planned deck structure without rendering slides."""
    try:
        if req.config.quality == QualityTier.PREMIUM:
            model = settings.PREMIUM_MODEL
        elif req.config.quality == QualityTier.DRAFT:
            model = settings.DRAFT_MODEL
        else:
            model = settings.DEFAULT_MODEL

        deck_plan = await planner.plan_deck(req.user_request, model)
        return deck_plan.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/slides/render")
async def render_slides(req: RenderSlidesRequest):
    """Render one or more slides for a given deck plan."""
    try:
        if req.config.quality == QualityTier.PREMIUM:
            model = settings.PREMIUM_MODEL
            max_concurrency = settings.PREMIUM_MAX_CONCURRENCY
        elif req.config.quality == QualityTier.DRAFT:
            model = settings.DRAFT_MODEL
            max_concurrency = settings.DRAFT_MAX_CONCURRENCY
        else:
            model = settings.DEFAULT_MODEL
            max_concurrency = settings.DEFAULT_MAX_CONCURRENCY

        slides = req.slides or req.deck_plan.slides
        candidate_map = req.candidate_map or {}

        template_catalog = get_template_html_catalog()
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
        if req.config.quality == QualityTier.PREMIUM:
            model = settings.PREMIUM_MODEL
        elif req.config.quality == QualityTier.DRAFT:
            model = settings.DRAFT_MODEL
        else:
            model = settings.DEFAULT_MODEL

        slide_spec = req.slide
        if slide_spec is None and req.slide_id is not None:
            slide_spec = next(
                (s for s in req.deck_plan.slides if s.slide_id == req.slide_id), None
            )
        if slide_spec is None:
            raise HTTPException(status_code=400, detail="Provide slide or slide_id")

        candidate_templates = req.candidate_templates
        if not candidate_templates:
            llm = make_llm(model=model)
            summaries = get_template_summaries()
            summaries_prompt = "\n".join(
                f"- {name}: {description}" for name, description in summaries.items()
            )
            user_request_for_preview = req.deck_plan.topic

            candidate_templates = await layout_selector.select_layout_for_slide(
                slide=slide_spec,
                deck_plan=req.deck_plan,
                user_request=user_request_for_preview,
                template_summaries_prompt=summaries_prompt,
                llm=llm,
            )

        template_catalog = get_template_html_catalog()
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


@router.post("/generate-stream")
async def generate_stream(req: GenerateRequest):
    """
    렌더가 완료되는 슬라이드부터 순차적으로 SSE로 스트리밍 전송합니다.
    """
    try:
        if req.config.quality == QualityTier.PREMIUM:
            model = settings.PREMIUM_MODEL
            default_cc = settings.PREMIUM_MAX_CONCURRENCY
        elif req.config.quality == QualityTier.DRAFT:
            model = settings.DRAFT_MODEL
            default_cc = settings.DRAFT_MAX_CONCURRENCY
        else:
            model = settings.DEFAULT_MODEL
            default_cc = settings.DEFAULT_MAX_CONCURRENCY

        max_concurrency = max(1, req.config.concurrency or default_cc)
        ordered = bool(req.config.ordered)

        deck_plan = await planner.plan_deck(req.user_prompt, model)
        deck_plan = await layout_selector.run_layout_selection_for_deck(
            deck_plan=deck_plan, user_request=req.user_prompt, model=model
        )

        template_catalog = get_template_html_catalog()

        async def sse_event(event: str, data: dict):
            payload = (
                f"event: {event}\n"
                + "data: "
                + json.dumps(data, ensure_ascii=False)
                + "\n\n"
            )
            return payload.encode("utf-8")

        async def event_generator():
            start = asyncio.get_event_loop().time()
            total = len(deck_plan.slides)
            completed = 0

            yield await sse_event(
                "started", {"total_slides": total, "model": model, "ordered": ordered}
            )
            yield await sse_event("deck_plan", deck_plan.model_dump())

            semaphore = asyncio.Semaphore(max_concurrency)
            queue: asyncio.Queue = asyncio.Queue()

            async def run_one(idx: int, slide_spec):
                async with semaphore:
                    try:
                        result: SlideHTML = await slide_worker.process_slide(
                            slide_spec=slide_spec,
                            deck_plan=deck_plan,
                            candidate_template_names=slide_spec.layout_candidates or [],
                            template_catalog=template_catalog,
                            model=model,
                        )
                        await queue.put((idx, slide_spec, result))
                    except Exception as e:
                        await queue.put((idx, slide_spec, e))

            tasks = [
                asyncio.create_task(run_one(idx, slide_spec))
                for idx, slide_spec in enumerate(deck_plan.slides)
            ]

            next_index = 0
            buffer: Dict[int, tuple] = {}

            try:
                while completed < total:
                    idx, spec, payload = await queue.get()

                    if isinstance(payload, Exception):
                        yield await sse_event(
                            "error",
                            {
                                "index": idx,
                                "slide_id": getattr(spec, "slide_id", None),
                                "message": str(payload),
                            },
                        )
                        completed += 1
                        yield await sse_event(
                            "progress", {"completed": completed, "total": total}
                        )
                        continue

                    if ordered:
                        buffer[idx] = (spec, payload)
                        while next_index in buffer:
                            s, res = buffer.pop(next_index)
                            completed += 1
                            yield await sse_event(
                                "slide_rendered",
                                {
                                    "index": next_index,
                                    "slide_id": res.slide_id,
                                    "title": s.title,
                                    "template_name": res.template_name,
                                    "html": res.html,
                                },
                            )
                            yield await sse_event(
                                "progress", {"completed": completed, "total": total}
                            )
                            next_index += 1
                    else:
                        completed += 1
                        yield await sse_event(
                            "slide_rendered",
                            {
                                "index": idx,
                                "slide_id": payload.slide_id,
                                "title": spec.title,
                                "template_name": payload.template_name,
                                "html": payload.html,
                            },
                        )
                        yield await sse_event(
                            "progress", {"completed": completed, "total": total}
                        )

                await asyncio.gather(*tasks, return_exceptions=True)
                duration = int((asyncio.get_event_loop().time() - start) * 1000)
                yield await sse_event(
                    "completed", {"total": total, "duration_ms": duration}
                )
            except asyncio.CancelledError:
                for t in tasks:
                    t.cancel()
                raise

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
