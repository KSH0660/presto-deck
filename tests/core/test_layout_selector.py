# tests/core/test_layout_selector.py

import pytest
from unittest.mock import patch, AsyncMock

from app.core.layout_selector import run_layout_selection_for_deck
from app.models.schema import DeckPlan, SlideSpec

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_deck_plan():
    """Provides a basic DeckPlan object for testing."""
    return DeckPlan(
        topic="Test Topic",
        audience="Test Audience",
        slides=[
            SlideSpec(slide_id=1, title="First Slide"),
            SlideSpec(slide_id=2, title="Second Slide"),
        ],
    )


async def test_run_layout_selection_for_deck(mock_deck_plan):
    """
    Tests the run_layout_selection_for_deck orchestrator function.

    It should:
    1. Get template summaries from the template manager.
    2. Call select_layout_for_slide for each slide in the deck.
    3. Update the layout_candidates field on each slide spec.
    """
    # Mock the dependencies
    with (
        patch("app.core.layout_selector.get_template_summaries") as mock_get_summaries,
        patch(
            "app.core.layout_selector.select_layout_for_slide", new_callable=AsyncMock
        ) as mock_select_for_slide,
    ):
        # Configure mock return values
        mock_get_summaries.return_value = {"test.html": "A test template"}
        # Make the mock return different values for each call to simulate variety
        mock_select_for_slide.side_effect = [
            ["template1.html", "template2.html"],  # For slide 1
            ["template3.html"],  # For slide 2
        ]

        # Execute the function
        updated_deck_plan = await run_layout_selection_for_deck(
            deck_plan=mock_deck_plan,
            user_request="Test user request",
            model="test-model",
        )

        # Assertions
        mock_get_summaries.assert_called_once()
        assert mock_select_for_slide.call_count == 2  # Called for each slide

        # Check that the original deck_plan object was modified and returned
        assert updated_deck_plan is mock_deck_plan

        # Check that the slides have the correct layout candidates
        assert updated_deck_plan.slides[0].layout_candidates == [
            "template1.html",
            "template2.html",
        ]
        assert updated_deck_plan.slides[1].layout_candidates == ["template3.html"]

        # Verify that select_layout_for_slide was called with the correct slide spec
        # The first positional argument to select_layout_for_slide is the slide spec.
        first_call_args = mock_select_for_slide.call_args_list[0]
        assert first_call_args.args[0].slide_id == 1

        second_call_args = mock_select_for_slide.call_args_list[1]
        assert second_call_args.args[0].slide_id == 2
