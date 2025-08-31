from __future__ import annotations

import asyncio
import time
from typing import List, Optional, AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from app.core.infra.config import settings
from app.core.infra.metrics import SLIDES_RENDERED
from app.core.pipeline.emitter import EventEmitter, sse_event
from app.core.infra.eventbus import ui_event_bus
from app.core.rendering.slide_worker import process_slide
from app.core.rendering.edit import edit_slide_content
from app.core.templates.template_manager import get_template_html_catalog
from app.core.storage.deck_store import get_deck_store
from app.models.schema import DeckPlan, SlideSpec, SlideHTML, GenerateRequest
from app.models.types import QualityTier
from app.core.planning import planner
from app.core.selection import layout_selector
import logging


router = APIRouter()
logger = logging.getLogger(__name__)


def _resolve_model(q: QualityTier) -> str:
    if q == QualityTier.PREMIUM:
        return settings.PREMIUM_MODEL
    if q == QualityTier.DRAFT:
        return settings.DRAFT_MODEL
    return settings.DEFAULT_MODEL


class DeckCreateRequest(GenerateRequest):
    """Create a deck by generating a plan from a user prompt."""

    user_prompt: str
    theme: Optional[str] = None
    color_preference: Optional[str] = None


@router.get("/decks")
async def list_decks() -> JSONResponse:
    store = get_deck_store()
    decks = await store.list_decks()
    return JSONResponse({"decks": decks})


@router.post("/decks")
async def create_deck(req: DeckCreateRequest) -> JSONResponse:
    """Plan a deck and persist it, returning the deck_id and plan."""
    # Plan then select layouts
    initial = await planner.plan_deck(req.user_prompt, model=settings.DEFAULT_MODEL)
    deck = await layout_selector.run_layout_selection_for_deck(
        initial_deck_plan=initial,
        user_request=req.user_prompt,
        model=settings.DEFAULT_MODEL,
    )
    # Apply overrides
    deck = DeckPlan(
        topic=deck.topic,
        audience=deck.audience,
        theme=req.theme or deck.theme,
        color_preference=req.color_preference or deck.color_preference,
        slides=deck.slides,
    )

    store = get_deck_store()
    deck_id = await store.create_deck(deck)
    logger.info("[DeckAPI] Created deck id=%s topic=%s", deck_id, deck.topic)
    return JSONResponse({"deck_id": deck_id, "deck_plan": deck.model_dump()})


@router.get("/decks/{deck_id}")
async def get_deck(deck_id: str) -> JSONResponse:
    store = get_deck_store()
    plan = await store.get_deck_plan(deck_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Deck not found")
    slides = await store.list_slides(deck_id)
    return JSONResponse(
        {
            "deck_id": deck_id,
            "deck_plan": plan.model_dump(),
            "slides": slides,
        }
    )


@router.put("/decks/{deck_id}/plan")
async def update_deck_plan(deck_id: str, plan: DeckPlan) -> JSONResponse:
    store = get_deck_store()
    await store.update_deck_plan(deck_id, plan)
    return JSONResponse({"deck_id": deck_id, "deck_plan": plan.model_dump()})


@router.get("/decks/{deck_id}/slides")
async def list_slides(deck_id: str) -> JSONResponse:
    store = get_deck_store()
    slides = await store.list_slides(deck_id)
    return JSONResponse(slides)


@router.get("/decks/{deck_id}/slides/{slide_id}")
async def get_slide(deck_id: str, slide_id: int) -> JSONResponse:
    """Return a single slide record for a deck."""
    store = get_deck_store()
    slide = await store.get_slide(deck_id, slide_id)
    if not slide:
        raise HTTPException(status_code=404, detail="Slide not found")
    return JSONResponse(slide)


class DeckRenderRequest(GenerateRequest):
    slides: Optional[List[SlideSpec]] = None


@router.post("/decks/{deck_id}/render/stream")
async def render_deck_stream(deck_id: str, req: DeckRenderRequest) -> StreamingResponse:
    """Render slides for a deck and stream SSE events, persisting to the deck store."""

    async def _event_stream() -> AsyncGenerator[bytes, None]:
        store = get_deck_store()
        plan = await store.get_deck_plan(deck_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Deck not found")

        queue: asyncio.Queue[str] = asyncio.Queue()
        emitter = EventEmitter(queue)

        model = _resolve_model(req.config.quality)
        catalog = get_template_html_catalog()
        targets: List[SlideSpec] = req.slides or plan.slides
        total_slides = len(targets)
        heartbeat_interval = max(5, int(settings.HEARTBEAT_INTERVAL_SEC))
        start = time.time()

        await emitter.emit(
            "started",
            {
                "model": model,
                "ordered": bool(req.config.ordered),
                "total": total_slides,
                "deck_id": deck_id,
            },
        )
        logger.info(
            "[DeckAPI] Render start deck id=%s model=%s total_slides=%d ordered=%s",
            deck_id,
            model,
            total_slides,
            bool(req.config.ordered),
        )
        await ui_event_bus.publish(
            "started", {"total": total_slides, "deck_id": deck_id}
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
                        deck_plan=plan,
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
                    yield (
                        await sse_event(
                            "heartbeat", {"ts": int(now), "deck_id": deck_id}
                        )
                    ).encode("utf-8")
                continue

            if isinstance(payload, Exception):
                await emitter.emit(
                    "error",
                    {
                        "index": idx,
                        "slide_id": getattr(spec, "slide_id", None),
                        "message": str(payload),
                        "deck_id": deck_id,
                    },
                )
            else:

                async def persist_and_emit(
                    _idx: int, _spec: SlideSpec, _res: SlideHTML
                ):
                    await emitter.emit(
                        "slide_rendered",
                        {
                            "index": _idx,
                            "slide_id": _res.slide_id,
                            "title": _spec.title,
                            "template_name": _res.template_name,
                            "html": _res.html,
                            "deck_id": deck_id,
                        },
                    )
                    await ui_event_bus.publish(
                        "slide_rendered",
                        {"slide_id": _res.slide_id, "deck_id": deck_id},
                    )
                    SLIDES_RENDERED.inc()
                    import time as _time

                    await store.add_or_update_slide(
                        deck_id,
                        {
                            "id": _spec.slide_id,
                            "title": _spec.title,
                            "html_content": _res.html,
                            "version": 1,
                            "versions": [
                                {
                                    "version": 1,
                                    "html": _res.html,
                                    "prompt": None,
                                    "ts": int(_time.time()),
                                }
                            ],
                            "status": "complete",
                        },
                    )
                    logger.debug(
                        "[DeckAPI] Slide persisted deck id=%s slide_id=%s title=%s",
                        deck_id,
                        _spec.slide_id,
                        _spec.title,
                    )

                if req.config.ordered:
                    buffer[idx] = (spec, payload)
                    while next_index in buffer:
                        s, res = buffer.pop(next_index)
                        await persist_and_emit(next_index, s, res)
                        next_index += 1
                else:
                    await persist_and_emit(idx, spec, payload)

            completed += 1
            await emitter.emit(
                "progress",
                {
                    "completed": completed,
                    "total": total_slides,
                    "stage": "rendering",
                    "deck_id": deck_id,
                },
            )

            while not queue.empty():
                yield (await queue.get()).encode("utf-8")

        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        duration_ms = int((time.time() - start) * 1000)
        payload = {
            "total": total_slides,
            "duration_ms": duration_ms,
            "deck_id": deck_id,
        }
        await ui_event_bus.publish("completed", payload)
        logger.info(
            "[DeckAPI] Render complete deck id=%s slides=%d duration_ms=%d",
            deck_id,
            total_slides,
            duration_ms,
        )
        yield (await sse_event("completed", payload)).encode("utf-8")

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/decks/{deck_id}/slides/{slide_id}/edit")
async def edit_slide(deck_id: str, slide_id: int, payload: dict) -> JSONResponse:
    store = get_deck_store()
    slide = await store.get_slide(deck_id, slide_id)
    if not slide:
        raise HTTPException(status_code=404, detail="Slide not found")
    edit_prompt = payload.get("edit_prompt") or ""
    if not isinstance(edit_prompt, str) or not edit_prompt.strip():
        raise HTTPException(status_code=400, detail="edit_prompt required")
    slide["status"] = "editing"
    try:
        new_html = await edit_slide_content(
            slide.get("html_content", ""), edit_prompt=edit_prompt
        )
        slide["html_content"] = new_html
        slide["version"] = int(slide.get("version", 0)) + 1
    finally:
        slide["status"] = "complete"
    await store.add_or_update_slide(deck_id, slide)
    return JSONResponse(slide)


@router.delete("/decks/{deck_id}/slides/{slide_id}")
async def delete_slide(deck_id: str, slide_id: int) -> JSONResponse:
    store = get_deck_store()
    await store.delete_slide(deck_id, slide_id)
    return JSONResponse({"ok": True})


@router.put("/decks/{deck_id}/slides/{slide_id}")
async def update_slide(deck_id: str, slide_id: int, payload: dict) -> JSONResponse:
    """Directly update slide fields such as html_content/title and bump version.

    This is used by the visual editor (e.g., GrapesJS) to save changes.
    """
    store = get_deck_store()
    slide = await store.get_slide(deck_id, slide_id)
    if not slide:
        raise HTTPException(status_code=404, detail="Slide not found")

    html_content = payload.get("html_content")
    title = payload.get("title")
    commit_message = payload.get("commit_message") or "editor_update"

    updated = False
    if isinstance(title, str) and title.strip():
        slide["title"] = title.strip()
        updated = True
    if isinstance(html_content, str):
        slide["html_content"] = html_content
        # append versions history
        import time as _time

        versions = slide.get("versions") or []
        new_version = int(slide.get("version", 0)) + 1
        versions.append(
            {
                "version": new_version,
                "html": html_content,
                "prompt": commit_message,
                "ts": int(_time.time()),
            }
        )
        slide["versions"] = versions
        slide["version"] = new_version
        updated = True

    if not updated:
        # No changes provided
        return JSONResponse(slide)

    await store.add_or_update_slide(deck_id, slide)
    return JSONResponse(slide)
