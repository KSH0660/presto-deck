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
from app.core.storage.deck_store import get_deck_store
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


@router.get("/ui/decks/{deck_id}/slides", response_class=Response)
async def deck_slides_partial(deck_id: str) -> Response:
    """Return slides HTML snippet for a specific deck (htmx-friendly)."""
    tmpl = env.get_template("slides_area.html")
    store = get_deck_store()
    slides = await store.list_slides(deck_id)
    html = tmpl.render(slides=slides, deck_id=deck_id)
    return Response(content=html, media_type="text/html")


# JSON endpoints for in-memory slides (non-deck workflow)
@router.get("/ui/slides/{slide_id}/json")
async def get_inmemory_slide_json(slide_id: int):
    slide = next((s for s in state.slides_db if s.get("id") == slide_id), None)
    if not slide:
        return Response(
            '{"detail":"Not found"}', media_type="application/json", status_code=404
        )
    from fastapi.responses import JSONResponse

    return JSONResponse(slide)


@router.put("/ui/slides/{slide_id}/json")
async def update_inmemory_slide_json(slide_id: int, payload: dict):
    slide = next((s for s in state.slides_db if s.get("id") == slide_id), None)
    if not slide:
        return Response(
            '{"detail":"Not found"}', media_type="application/json", status_code=404
        )

    title = payload.get("title")
    html = payload.get("html_content")
    msg = payload.get("commit_message") or "editor_update"

    updated = False
    if isinstance(title, str) and title.strip():
        slide["title"] = title.strip()
        updated = True
    if isinstance(html, str):
        slide["html_content"] = html
        import time as _time

        versions = slide.get("versions") or []
        new_version = int(slide.get("version", 0)) + 1
        versions.append(
            {
                "version": new_version,
                "html": html,
                "prompt": msg,
                "ts": int(_time.time()),
            }
        )
        slide["versions"] = versions
        slide["version"] = new_version
        updated = True

    from fastapi.responses import JSONResponse

    if not updated:
        return JSONResponse(slide)
    return JSONResponse(slide)


@router.get("/ui/slides/{slide_id}", response_class=Response)
async def slide_card_partial(
    slide_id: int, preview_version: int | None = None
) -> Response:
    slide = next((s for s in state.slides_db if s.get("id") == slide_id), None)
    if not slide:
        return Response("", media_type="text/html", status_code=404)
    tmpl = env.get_template("slide_card.html")
    # Resolve preview_html if requested
    preview_html = None
    if preview_version is not None:
        for v in slide.get("versions") or []:
            try:
                if int(v.get("version")) == int(preview_version):
                    preview_html = v.get("html")
                    break
            except Exception:
                continue
    html = tmpl.render(slide=slide, preview_html=preview_html)
    return Response(content=html, media_type="text/html")


@router.get("/ui/decks/{deck_id}/slides/{slide_id}", response_class=Response)
async def deck_slide_card_partial(
    deck_id: str, slide_id: int, preview_version: int | None = None
) -> Response:
    store = get_deck_store()
    slide = await store.get_slide(deck_id, slide_id)
    if not slide:
        return Response("", media_type="text/html", status_code=404)
    tmpl = env.get_template("slide_card.html")
    preview_html = None
    if preview_version is not None:
        for v in slide.get("versions") or []:
            try:
                if int(v.get("version")) == int(preview_version):
                    preview_html = v.get("html")
                    break
            except Exception:
                continue
    html = tmpl.render(slide=slide, deck_id=deck_id, preview_html=preview_html)
    return Response(content=html, media_type="text/html")


@router.post("/ui/decks/{deck_id}/slides/{slide_id}/edit", response_class=Response)
async def edit_deck_slide_html(
    deck_id: str, slide_id: int, edit_prompt: str = Form(...)
) -> Response:
    store = get_deck_store()
    slide = await store.get_slide(deck_id, slide_id)
    if not slide:
        return Response("", media_type="text/html", status_code=404)
    slide["status"] = "editing"
    try:
        new_html = await edit_slide_content(
            slide.get("html_content", ""), edit_prompt=edit_prompt
        )
        # Stash the proposed edit and keep current as-is until user decides
        slide["pending_html"] = new_html
        slide["previous_html"] = slide.get("html_content", "")
        slide["pending_prompt"] = edit_prompt
    finally:
        slide["status"] = "complete"
    await store.add_or_update_slide(deck_id, slide)
    tmpl = env.get_template("slide_card.html")
    html = tmpl.render(slide=slide, deck_id=deck_id)
    return Response(content=html, media_type="text/html")


@router.post(
    "/ui/decks/{deck_id}/slides/{slide_id}/apply_edit", response_class=Response
)
async def apply_edit_deck_slide_html(
    deck_id: str, slide_id: int, decision: str = Form(...)
) -> Response:
    """Apply or discard a pending edit for a deck slide.

    decision: "accept" to replace with edited version, "reject" to keep previous.
    """
    store = get_deck_store()
    slide = await store.get_slide(deck_id, slide_id)
    if not slide:
        return Response("", media_type="text/html", status_code=404)

    # Normalize decision
    d = (decision or "").strip().lower()
    if d not in ("accept", "reject"):
        d = "reject"

    if slide.get("pending_html") is not None:
        if d == "accept":
            import time as _time

            new_version = int(slide.get("version", 0)) + 1
            new_html = slide.get("pending_html")
            # append to versions history
            versions = (slide.get("versions") or []) + [
                {
                    "version": new_version,
                    "html": new_html,
                    "prompt": slide.get("pending_prompt"),
                    "ts": int(_time.time()),
                }
            ]
            slide["versions"] = versions
            slide["html_content"] = new_html
            slide["version"] = new_version
        # Clear pending regardless of decision
        slide.pop("pending_html", None)
        slide.pop("previous_html", None)
        slide.pop("pending_prompt", None)
    await store.add_or_update_slide(deck_id, slide)

    tmpl = env.get_template("slide_card.html")
    html = tmpl.render(slide=slide, deck_id=deck_id)
    return Response(content=html, media_type="text/html")


@router.delete("/ui/decks/{deck_id}/slides/{slide_id}/delete", response_class=Response)
async def delete_deck_slide_ui(deck_id: str, slide_id: int) -> Response:
    store = get_deck_store()
    await store.delete_slide(deck_id, slide_id)
    return Response("", media_type="text/html", status_code=200)


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

    # Create the deck and get the ID
    store = get_deck_store()
    deck_id = await store.create_deck(deck)

    tmpl = env.get_template("deck_plan_editor.html")
    deck_with_id = deck.model_dump()
    deck_with_id["deck_id"] = deck_id
    html = tmpl.render(deck=deck_with_id, user_prompt=user_prompt)
    return Response(html, media_type="text/html")


@router.put("/ui/decks/{deck_id}/plan", response_class=Response)
async def update_deck_plan_ui(deck_id: str, request: Request) -> Response:
    """Update a deck plan from the editor form."""
    form_data = await request.form()
    deck_plan = _parse_deck_from_form(form_data)
    store = get_deck_store()
    await store.update_deck_plan(deck_id, deck_plan)

    # Re-render the editor to reflect the changes
    tmpl = env.get_template("deck_plan_editor.html")
    # The deck object passed to the template needs a deck_id
    deck_with_id = deck_plan.model_dump()
    deck_with_id["deck_id"] = deck_id
    html = tmpl.render(deck=deck_with_id)
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
            slide.get("html_content", ""), edit_prompt=edit_prompt
        )
        slide["pending_html"] = new_html
        slide["previous_html"] = slide.get("html_content", "")
        slide["pending_prompt"] = edit_prompt
    finally:
        slide["status"] = "complete"
    tmpl = env.get_template("slide_card.html")
    html = tmpl.render(slide=slide)
    return Response(html, media_type="text/html")


@router.post("/ui/slides/{slide_id}/apply_edit", response_class=Response)
async def apply_edit_slide_html(slide_id: int, decision: str = Form(...)) -> Response:
    """Apply or discard a pending edit for non-deck slide cards (in-memory)."""
    slide = next((s for s in state.slides_db if s.get("id") == slide_id), None)
    if not slide:
        return Response("", media_type="text/html", status_code=404)

    d = (decision or "").strip().lower()
    if d not in ("accept", "reject"):
        d = "reject"

    if slide.get("pending_html") is not None:
        if d == "accept":
            import time as _time

            new_version = int(slide.get("version", 0)) + 1
            new_html = slide.get("pending_html")
            versions = (slide.get("versions") or []) + [
                {
                    "version": new_version,
                    "html": new_html,
                    "prompt": slide.get("pending_prompt"),
                    "ts": int(_time.time()),
                }
            ]
            slide["versions"] = versions
            slide["html_content"] = new_html
            slide["version"] = new_version
        slide.pop("pending_html", None)
        slide.pop("previous_html", None)
        slide.pop("pending_prompt", None)

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


@router.get("/ui/decks/{deck_id}/events")
async def ui_deck_events(deck_id: str):
    """Deck-scoped SSE endpoint that filters events by deck_id in data payload."""
    import time
    import asyncio as _asyncio
    from fastapi.responses import StreamingResponse

    async def gen():
        q = ui_event_bus.subscribe()
        try:
            yield (
                await sse_event("hello", {"ts": int(time.time()), "deck_id": deck_id})
            ).encode("utf-8")
            last_hb = time.time()
            while True:
                try:
                    msg = await _asyncio.wait_for(q.get(), timeout=15)
                    # Filter by deck_id by peeking JSON in data line
                    try:
                        # msg is an SSE string with 'data: {json}\n\n'
                        data_line = next(
                            (ln for ln in msg.split("\n") if ln.startswith("data:")),
                            None,
                        )
                        if data_line is not None:
                            import json as _json

                            payload = _json.loads(data_line[5:].strip())
                            if payload.get("deck_id") not in (None, deck_id):
                                # skip events for other decks
                                continue
                    except Exception:
                        pass
                    yield msg.encode("utf-8")
                    last_hb = time.time()
                except _asyncio.TimeoutError:
                    now = time.time()
                    if now - last_hb >= 15:
                        yield (
                            await sse_event(
                                "heartbeat", {"ts": int(now), "deck_id": deck_id}
                            )
                        ).encode("utf-8")
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
