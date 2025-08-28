# tests/core/test_layout_selector.py

import pytest
from unittest.mock import patch, AsyncMock

from app.core.layout_selector import run_layout_selection_for_deck
from app.models.schema import InitialDeckPlan, SlideContent, SlideSpec, DeckPlan

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_initial_deck_plan():
    """Provides a basic InitialDeckPlan object for testing."""
    return InitialDeckPlan(
        topic="Test Topic",
        audience="Test Audience",
        slides=[
            SlideContent(slide_id=1, title="First Slide"),
            SlideContent(slide_id=2, title="Second Slide"),
        ],
    )


async def test_run_layout_selection_for_deck(mock_initial_deck_plan):
    """
    Tests the run_layout_selection_for_deck orchestrator function.

    It should:
    1. Take an InitialDeckPlan.
    2. Call select_layout_for_slide for each slide content.
    3. Return a new, complete DeckPlan object with layout candidates.
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

        # The mock now needs to return complete SlideSpec objects
        slide_content_1 = mock_initial_deck_plan.slides[0]
        slide_content_2 = mock_initial_deck_plan.slides[1]

        mock_select_for_slide.side_effect = [
            SlideSpec(
                **slide_content_1.model_dump(),
                layout_candidates=["template1.html", "template2.html"],
            ),
            SlideSpec(
                **slide_content_2.model_dump(),
                layout_candidates=["template3.html"],
            ),
        ]

        # Execute the function
        final_deck_plan = await run_layout_selection_for_deck(
            initial_deck_plan=mock_initial_deck_plan,
            user_request="Test user request",
            model="test-model",
        )

        # Assertions
        mock_get_summaries.assert_called_once()
        assert mock_select_for_slide.call_count == 2  # Called for each slide

        # Check that a new DeckPlan object is returned with the correct data
        assert isinstance(final_deck_plan, DeckPlan)
        assert final_deck_plan is not mock_initial_deck_plan
        assert final_deck_plan.topic == mock_initial_deck_plan.topic
        assert len(final_deck_plan.slides) == 2

        # Check that the slides have the correct layout candidates
        assert final_deck_plan.slides[0].layout_candidates == [
            "template1.html",
            "template2.html",
        ]
        assert final_deck_plan.slides[1].layout_candidates == ["template3.html"]
        assert final_deck_plan.slides[0].title == "First Slide" # Ensure content is preserved

        # Verify that select_layout_for_slide was called with the correct slide content
        first_call_args = mock_select_for_slide.call_args_list[0]
        assert first_call_args.args[0].slide_id == 1
        assert isinstance(first_call_args.args[0], SlideContent)

        second_call_args = mock_select_for_slide.call_args_list[1]
        assert second_call_args.args[0].slide_id == 2
        assert isinstance(second_call_args.args[0], SlideContent)
