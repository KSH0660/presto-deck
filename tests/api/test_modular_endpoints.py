# tests/api/test_modular_endpoints.py

import pytest
from unittest.mock import patch, AsyncMock

from app.models.schema import (
    DeckPlan,
    SlideSpec,
    LayoutSelection,
    SlideCandidates,
    TemplateCandidate,
    SlideHTML,
)


pytestmark = pytest.mark.asyncio


@pytest.fixture
def sample_deck_plan():
    return DeckPlan(
        topic="Sample Topic",
        audience="Executives",
        slides=[
            SlideSpec(slide_id=1, title="Intro", key_points=["A"]),
            SlideSpec(slide_id=2, title="Body", key_points=["B"]),
        ],
    )


@pytest.fixture
def sample_selection():
    return LayoutSelection(
        items=[
            SlideCandidates(
                slide_id=1, candidates=[TemplateCandidate(template_name="title.html")]
            ),
            SlideCandidates(
                slide_id=2, candidates=[TemplateCandidate(template_name="content.html")]
            ),
        ]
    )


async def test_plan_endpoint_success(client, sample_deck_plan):
    with patch("app.core.planner.plan_deck", new_callable=AsyncMock) as mock_plan:
        mock_plan.return_value = sample_deck_plan

        resp = await client.post(
            "/api/v1/plan",
            json={"user_request": "Make a deck", "quality": "default"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["topic"] == "Sample Topic"
        mock_plan.assert_called_once()


async def test_layouts_select_endpoint_success(
    client, sample_deck_plan, sample_selection
):
    with patch(
        "app.core.layout_selector.select_layouts", new_callable=AsyncMock
    ) as mock_select:
        mock_select.return_value = sample_selection

        resp = await client.post(
            "/api/v1/layouts/select",
            json={"deck_plan": sample_deck_plan.model_dump(), "quality": "default"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        mock_select.assert_called_once()


async def test_render_slides_endpoint_success(client, sample_deck_plan):
    with patch(
        "app.core.slide_worker.process_slide", new_callable=AsyncMock
    ) as mock_process:
        mock_process.side_effect = [
            SlideHTML(slide_id=1, template_name="title.html", html="<h1>One</h1>"),
            SlideHTML(slide_id=2, template_name="content.html", html="<p>Two</p>"),
        ]

        resp = await client.post(
            "/api/v1/slides/render",
            json={
                "deck_plan": sample_deck_plan.model_dump(),
                "quality": "default",
                "candidate_map": {"1": ["title.html"], "2": ["content.html"]},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["slides"]) == 2
        assert data["slides"][0]["html"].startswith("<h1>")
        assert mock_process.call_count == 2


async def test_preview_endpoint_auto_selects_candidates(
    client, sample_deck_plan, sample_selection
):
    with patch(
        "app.core.layout_selector.select_layouts", new_callable=AsyncMock
    ) as mock_select:
        with patch(
            "app.core.slide_worker.process_slide", new_callable=AsyncMock
        ) as mock_process:
            mock_select.return_value = sample_selection
            mock_process.return_value = SlideHTML(
                slide_id=1, template_name="title.html", html="<h1>Preview</h1>"
            )

            resp = await client.post(
                "/api/v1/preview",
                json={
                    "deck_plan": sample_deck_plan.model_dump(),
                    "slide_id": 1,
                    "quality": "default",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["template_name"] == "title.html"
            mock_select.assert_called_once()
            mock_process.assert_called_once()
