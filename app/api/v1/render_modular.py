from typing import List, Optional, AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from app.models.schema import DeckPlan, SlideSpec, SlideHTML, GenerateRequest
from app.core.rendering.slide_worker import process_slide
from app.core.templates.template_manager import get_template_html_catalog
from app.core.infra.config import settings
from app.models.types import QualityTier
from app.core.infra import state
from app.core.pipeline.emitter import EventEmitter, sse_event
from app.core.infra.metrics import SLIDES_RENDERED
import asyncio
import time

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


@router.post("/slides/render/stream")
async def render_slides_stream(req: RenderRequest) -> StreamingResponse:
    """Render slides in parallel and stream SSE events (similar to /generate)."""

    async def _event_stream() -> AsyncGenerator[bytes, None]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        emitter = EventEmitter(queue)

        model = _resolve_model(req.config.quality)
        catalog = get_template_html_catalog()
        targets: List[SlideSpec] = req.slides or req.deck_plan.slides
        total_slides = len(targets)
        heartbeat_interval = max(5, int(settings.HEARTBEAT_INTERVAL_SEC))
        start = time.time()

        await emitter.emit(
            "started",
            {
                "model": model,
                "ordered": bool(req.config.ordered),
                "total": total_slides,
            },
        )

        semaphore = asyncio.Semaphore(
            min(
                settings.MAX_CONCURRENCY_LIMIT,
                max(1, req.config.concurrency or settings.DEFAULT_MAX_CONCURRENCY),
            )
        )
        results_q: asyncio.Queue = asyncio.Queue()

        async def run_one(idx: int, spec: SlideSpec):
            async with semaphore:
                try:
                    html = await process_slide(
                        slide_spec=spec,
                        deck_plan=req.deck_plan,
                        req=req,
                        template_catalog=catalog,
                        model=model,
                    )
                    await results_q.put((idx, spec, html))
                except Exception as e:  # pragma: no cover - defensive
                    await results_q.put((idx, spec, e))

        tasks = [asyncio.create_task(run_one(i, s)) for i, s in enumerate(targets)]

        completed = 0
        next_index = 0
        buffer: dict[int, tuple] = {}
        last_heartbeat = time.time()

        while completed < total_slides:
            try:
                idx, spec, payload = await asyncio.wait_for(
                    results_q.get(), timeout=heartbeat_interval
                )
            except asyncio.TimeoutError:
                now = time.time()
                if now - last_heartbeat >= heartbeat_interval:
                    last_heartbeat = now
                    yield (await sse_event("heartbeat", {"ts": int(now)})).encode(
                        "utf-8"
                    )
                continue

            if isinstance(payload, Exception):
                await emitter.emit(
                    "error",
                    {
                        "index": idx,
                        "slide_id": getattr(spec, "slide_id", None),
                        "message": str(payload),
                    },
                )
            else:
                if req.config.ordered:
                    buffer[idx] = (spec, payload)
                    while next_index in buffer:
                        s, res = buffer.pop(next_index)
                        await emitter.emit(
                            "slide_rendered",
                            {
                                "index": next_index,
                                "slide_id": res.slide_id,
                                "title": s.title,
                                "template_name": res.template_name,
                                "html": res.html,
                            },
                        )
                        SLIDES_RENDERED.inc()
                        state.slides_db.append(
                            {
                                "id": s.slide_id,
                                "title": s.title,
                                "html_content": res.html,
                                "version": 1,
                                "status": "complete",
                            }
                        )
                        next_index += 1
                else:
                    await emitter.emit(
                        "slide_rendered",
                        {
                            "index": idx,
                            "slide_id": payload.slide_id,
                            "title": spec.title,
                            "template_name": payload.template_name,
                            "html": payload.html,
                        },
                    )
                    SLIDES_RENDERED.inc()
                    state.slides_db.append(
                        {
                            "id": spec.slide_id,
                            "title": spec.title,
                            "html_content": payload.html,
                            "version": 1,
                            "status": "complete",
                        }
                    )

            completed += 1
            await emitter.emit(
                "progress",
                {"completed": completed, "total": total_slides, "stage": "rendering"},
            )

            # drain events to client
            while not queue.empty():
                yield (await queue.get()).encode("utf-8")

        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        try:
            if state.slides_db:
                state.reset_slide_ids(max(s.get("id", 0) for s in state.slides_db) + 1)
        except Exception:
            pass

        duration_ms = int((time.time() - start) * 1000)
        yield (
            await sse_event(
                "completed", {"total": total_slides, "duration_ms": duration_ms}
            )
        ).encode("utf-8")

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
