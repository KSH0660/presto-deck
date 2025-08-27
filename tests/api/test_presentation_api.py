# tests/api/test_presentation_api.py

import pytest
from unittest.mock import patch, AsyncMock

from app.models.schema import DeckPlan, SlideSpec, SlideHTML

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


async def test_generate_presentation_success(client, mock_deck_plan):
    """Test the successful generation of a presentation with the new workflow."""
    # Simulate the output of the layout selector, which adds candidates to the plan
    plan_with_candidates = mock_deck_plan.model_copy(deep=True)
    plan_with_candidates.slides[0].layout_candidates = ["title.html"]
    plan_with_candidates.slides[1].layout_candidates = ["content.html"]

    with (
        patch("app.core.planner.plan_deck", new_callable=AsyncMock) as mock_plan,
        patch(
            "app.core.layout_selector.run_layout_selection_for_deck",
            new_callable=AsyncMock,
        ) as mock_run_layout,
        patch(
            "app.core.slide_worker.process_slide", new_callable=AsyncMock
        ) as mock_process,
    ):
        # Configure mock return values
        mock_plan.return_value = mock_deck_plan
        mock_run_layout.return_value = plan_with_candidates
        mock_process.side_effect = [
            SlideHTML(slide_id=1, template_name="title.html", html="<h1>Slide 1</h1>"),
            SlideHTML(slide_id=2, template_name="content.html", html="<p>Slide 2</p>"),
        ]

        # Make the API call with the new request format
        response = await client.post(
            "/api/v1/generate",
            json={"user_prompt": "Test presentation", "config": {"quality": "default"}},
        )

        # Assertions
        assert response.status_code == 200

        response_data = response.json()
        assert response_data["topic"] == "Test Topic"
        assert len(response_data["slides"]) == 2

        # Check that the final response contains both plan data and rendered HTML
        assert response_data["slides"][0]["title"] == "Slide 1"
        assert response_data["slides"][0]["html"] == "<h1>Slide 1</h1>"
        assert response_data["slides"][1]["title"] == "Slide 2"
        assert response_data["slides"][1]["html"] == "<p>Slide 2</p>"

        # Assert that our mocks were called correctly
        mock_plan.assert_called_once()
        mock_run_layout.assert_called_once_with(
            deck_plan=mock_deck_plan,
            user_request="Test presentation",
            model="gpt-5-mini",
        )
        assert mock_process.call_count == 2

        # Check that process_slide was called with the candidates from the layout step
        first_call_args = mock_process.call_args_list[0]
        assert first_call_args.kwargs["candidate_template_names"] == ["title.html"]
