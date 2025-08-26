# tests/core/test_layout_selector.py

import pytest
from unittest.mock import patch, AsyncMock

from app.core.layout_selector import select_layouts
from app.models.schema import (
    DeckPlan,
    SlideSpec,
    LayoutSelection,
    SlideCandidates,
    TemplateCandidate,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_deck_plan():
    return DeckPlan(
        topic="Test Topic",
        audience="Test Audience",
        slides=[SlideSpec(slide_id=1, title="Test")],
    )


async def test_select_layouts(mock_deck_plan):
    """Test the select_layouts function."""
    mock_result_selection = LayoutSelection(
        items=[
            SlideCandidates(
                slide_id=1, candidates=[TemplateCandidate(template_name="test.html")]
            )
        ]
    )

    with patch("app.core.layout_selector.build_selector_chain") as mock_build_chain:
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = mock_result_selection
        mock_build_chain.return_value = mock_chain

        # Mock load_template_catalog as it involves file I/O
        with patch(
            "app.core.layout_selector.load_template_catalog"
        ) as mock_load_catalog:
            mock_load_catalog.return_value = {"test.html": "<div></div>"}

            selection = await select_layouts(
                deck_plan=mock_deck_plan, model="test-model"
            )

            mock_build_chain.assert_called_once()
            mock_chain.ainvoke.assert_called_once()
            assert selection.items[0].slide_id == 1
            assert selection.items[0].candidates[0].template_name == "test.html"
