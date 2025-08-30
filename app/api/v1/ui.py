from fastapi import APIRouter, Response, Request, Form, UploadFile, File
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path

from app.core.infra import state
from app.core.planning import planner
from app.core.selection import layout_selector
from app.models.schema import DeckPlan, SlideSpec
from app.core.rendering.edit import edit_slide_content
from app.core.infra.config import settings
from app.core.infra.eventbus import ui_event_bus
from app.core.pipeline.emitter import sse_event

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "web" / "templates"
env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=select_autoescape(["html"])
)


@router.get("/ui/slides", response_class=Response)
async def slides_partial() -> Response:
    """Return HTML snippet for the slides area (htmx-friendly)."""
    tmpl = env.get_template("slides_area.html")
    html = tmpl.render(slides=state.slides_db)
    return Response(content=html, media_type="text/html")


@router.get("/ui/slides/{slide_id}", response_class=Response)
async def slide_card_partial(slide_id: int) -> Response:
    slide = next((s for s in state.slides_db if s.get("id") == slide_id), None)
    if not slide:
        return Response("", media_type="text/html", status_code=404)
    tmpl = env.get_template("slide_card.html")
    html = tmpl.render(slide=slide)
    return Response(content=html, media_type="text/html")


@router.post("/ui/plan_form", response_class=Response)
async def plan_form(
    request: Request,
    user_prompt: str = Form(...),
    theme: str | None = Form(None),
    color_preference: str | None = Form(None),
    files: list[UploadFile] | None = File(None),
) -> Response:
    """Accepts a simple form and returns a DeckPlan editor partial."""
    # Generate initial + select layouts
    initial = await planner.plan_deck(user_prompt, model=settings.DEFAULT_MODEL)
    deck = await layout_selector.run_layout_selection_for_deck(
        initial_deck_plan=initial,
        user_request=user_prompt,
        model=settings.DEFAULT_MODEL,
    )
    # Override with user-provided style if present
    deck = DeckPlan(
        topic=deck.topic,
        audience=deck.audience,
        theme=theme or deck.theme,
        color_preference=color_preference or deck.color_preference,
        slides=deck.slides,
    )
    tmpl = env.get_template("deck_plan_editor.html")
    html = tmpl.render(deck=deck)
    return Response(html, media_type="text/html")


def _parse_deck_from_form(form: dict) -> DeckPlan:
    topic = form.get("topic", "")
    audience = form.get("audience", "")
    theme = form.get("theme") or None
    color = form.get("color_preference") or None
    # Slides as slides[index][field]
    slides: list[SlideSpec] = []
    # collect indices
    import re

    idxs = set()
    for k in form.keys():
        m = re.match(r"slides\[(\d+)\]", k)
        if m:
            idxs.add(int(m.group(1)))
    for i in sorted(list(idxs)):
        sid = int(form.get(f"slides[{i}][slide_id]", i + 1))
        title = form.get(f"slides[{i}][title]", "")
        key_points_raw = form.get(f"slides[{i}][key_points]", "")
        numbers_raw = form.get(f"slides[{i}][numbers]", "")
        notes = form.get(f"slides[{i}][notes]", "") or None
        section = form.get(f"slides[{i}][section]", "") or None
        layout_raw = form.get(f"slides[{i}][layout_candidates]", "")
        key_points = [p.strip() for p in key_points_raw.split("\n") if p.strip()]
        try:
            import json

            numbers = json.loads(numbers_raw) if numbers_raw.strip() else None
        except Exception:
            numbers = None
        layout_candidates = [p.strip() for p in layout_raw.split(",") if p.strip()]
        slides.append(
            SlideSpec(
                slide_id=sid,
                title=title,
                key_points=key_points or None,
                numbers=numbers,
                notes=notes,
                section=section,
                layout_candidates=layout_candidates or None,
            )
        )
    return DeckPlan(
        topic=topic,
        audience=audience,
        theme=theme,
        color_preference=color,
        slides=slides,
    )


@router.post("/ui/slides/{slide_id}/edit", response_class=Response)
async def edit_slide_html(slide_id: int, edit_prompt: str = Form(...)) -> Response:
    slide = next((s for s in state.slides_db if s.get("id") == slide_id), None)
    if not slide:
        return Response("", media_type="text/html", status_code=404)
    slide["status"] = "editing"
    try:
        new_html = await edit_slide_content(
            slide["html_content"], edit_prompt=edit_prompt
        )
        slide["html_content"] = new_html
        slide["version"] = int(slide.get("version", 0)) + 1
    finally:
        slide["status"] = "complete"
    tmpl = env.get_template("slide_card.html")
    html = tmpl.render(slide=slide)
    return Response(html, media_type="text/html")


@router.delete("/ui/slides/{slide_id}/delete", response_class=Response)
async def delete_slide_ui(slide_id: int) -> Response:
    before = len(state.slides_db)
    state.slides_db = [s for s in state.slides_db if s.get("id") != slide_id]
    status = 200 if len(state.slides_db) < before else 404
    return Response("", media_type="text/html", status_code=status)


@router.get("/ui/events")
async def ui_events():
    import time
    import asyncio as _asyncio
    from fastapi.responses import StreamingResponse

    async def gen():
        q = ui_event_bus.subscribe()
        try:
            yield (await sse_event("hello", {"ts": int(time.time())})).encode("utf-8")
            last_hb = time.time()
            while True:
                try:
                    msg = await _asyncio.wait_for(q.get(), timeout=15)
                    yield msg.encode("utf-8")
                    last_hb = time.time()
                except _asyncio.TimeoutError:
                    now = time.time()
                    if now - last_hb >= 15:
                        yield (await sse_event("heartbeat", {"ts": int(now)})).encode(
                            "utf-8"
                        )
                        last_hb = now
        finally:
            ui_event_bus.unsubscribe(q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
