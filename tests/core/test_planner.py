# tests/core/test_planner.py

import pytest
from unittest.mock import patch, AsyncMock

from app.core.planning.planner import plan_deck
from app.models.schema import InitialDeckPlan, SlideContent

pytestmark = pytest.mark.asyncio


async def test_plan_deck():
    """Test the plan_deck function.

    This test mocks the LLM chain to ensure the function correctly
    processes the input and returns a valid DeckPlan object.
    """
    # The expected return value from the mocked LLM call
    mock_result_plan = InitialDeckPlan(
        topic="Mocked Topic",
        audience="Mocked Audience",
        slides=[SlideContent(slide_id=1, title="Test Slide")],
    )

    # Patch the build_planner_chain to return a mock chain
    with patch("app.core.planning.planner.build_planner_chain") as mock_build_chain:
        # Create a mock chain with an AsyncMock for ainvoke
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = mock_result_plan
        mock_build_chain.return_value = mock_chain

        # Call the function being tested
        deck_plan = await plan_deck(user_request="Test request", model="test-model")

        # Assertions
        mock_build_chain.assert_called_once()
        mock_chain.ainvoke.assert_called_once()
        assert deck_plan.topic == "Mocked Topic"
        assert len(deck_plan.slides) == 1
        assert deck_plan.slides[0].title == "Test Slide"
