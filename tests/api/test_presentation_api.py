# tests/api/test_presentation_api.py

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

# Mark all tests in this file as asyncio tests
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_deck_plan():
    """Fixture for a sample DeckPlan."""
    return DeckPlan(
        topic="Test Topic",
        audience="Test Audience",
        slides=[
            SlideSpec(slide_id=1, title="Slide 1", key_points=["Point 1"]),
            SlideSpec(slide_id=2, title="Slide 2", key_points=["Point 2"]),
        ],
    )


@pytest.fixture
def mock_layout_selection():
    """Fixture for a sample LayoutSelection."""
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


@pytest.fixture
def mock_slide_html():
    """Fixture for a sample SlideHTML."""
    return SlideHTML(slide_id=1, template_name="title.html", html="<h1>Slide 1</h1>")


async def test_generate_presentation_success(
    client, mock_deck_plan, mock_layout_selection, mock_slide_html
):
    """Test the successful generation of a presentation."""
    with patch("app.core.planner.plan_deck", new_callable=AsyncMock) as mock_plan:
        with patch(
            "app.core.layout_selector.select_layouts", new_callable=AsyncMock
        ) as mock_select:
            with patch(
                "app.core.slide_worker.process_slide", new_callable=AsyncMock
            ) as mock_process:

                # Configure mock return values
                mock_plan.return_value = mock_deck_plan
                mock_select.return_value = mock_layout_selection
                # Let's make process_slide return a slightly different object for each slide
                mock_process.side_effect = [
                    SlideHTML(
                        slide_id=1, template_name="title.html", html="<h1>Slide 1</h1>"
                    ),
                    SlideHTML(
                        slide_id=2, template_name="content.html", html="<p>Slide 2</p>"
                    ),
                ]

                # Make the API call
                response = await client.post(
                    "/api/v1/generate",
                    json={"user_request": "Test presentation", "quality": "default"},
                )

                # Assertions
                assert response.status_code == 200

                response_data = response.json()
                assert response_data["topic"] == "Test Topic"
                assert len(response_data["slides"]) == 2
                assert response_data["slides"][0]["html"] == "<h1>Slide 1</h1>"
                assert response_data["slides"][1]["html"] == "<p>Slide 2</p>"

                # Assert that our mocks were called correctly
                mock_plan.assert_called_once_with("Test presentation", "gpt-4o-mini")
                mock_select.assert_called_once_with(mock_deck_plan, "gpt-4o-mini")
                assert mock_process.call_count == 2
