import pytest
from unittest.mock import patch, AsyncMock

from app.models.schema import (
    InitialDeckPlan,
    SlideContent,
    DeckPlan,
    SlideSpec,
    SlideHTML,
)


pytestmark = pytest.mark.asyncio


async def test_plan_endpoint(client):
    initial = InitialDeckPlan(
        topic="T",
        audience="A",
        slides=[SlideContent(slide_id=1, title="S1")],
    )
    final = DeckPlan(
        topic="T",
        audience="A",
        slides=[SlideSpec(slide_id=1, title="S1", layout_candidates=["x.html"])],
    )
    with (
        patch(
            "app.core.planning.planner.plan_deck", new=AsyncMock(return_value=initial)
        ),
        patch(
            "app.core.selection.layout_selector.run_layout_selection_for_deck",
            new=AsyncMock(return_value=final),
        ),
    ):
        payload = {"user_prompt": "hello", "config": {"quality": "default"}}
        resp = await client.post("/api/v1/plan", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["topic"] == "T"
        assert len(data["slides"]) == 1
        assert data["slides"][0]["layout_candidates"] == ["x.html"]


async def test_render_from_plan_endpoint(client):
    deck = DeckPlan(
        topic="T",
        audience="A",
        slides=[SlideSpec(slide_id=1, title="S1", layout_candidates=["x.html"])],
    )

    fake_html = SlideHTML(slide_id=1, template_name="x.html", html="<div>ok</div>")
    with patch(
        "app.core.rendering.slide_worker.process_slide",
        new=AsyncMock(return_value=fake_html),
    ):
        payload = {
            "user_prompt": "hello",
            "deck_plan": deck.model_dump(),
            "config": {"quality": "default"},
        }
        resp = await client.post("/api/v1/slides/render", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "slides" in data and len(data["slides"]) == 1
        assert data["slides"][0]["template_name"] == "x.html"


async def test_session_create_with_file(client, tmp_path):
    # httpx AsyncClient supports files with tuple(name, bytes, type)
    files = {"files": ("note.txt", b"hello", "text/plain")}
    form = {
        "user_prompt": "topic",
        "theme": "Minimal",
        "color_preference": "Blue",
    }
    resp = await client.post("/api/v1/session", files=files, data=form)
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data and data["files_saved"] == 1
