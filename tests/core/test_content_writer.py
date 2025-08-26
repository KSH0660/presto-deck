# tests/core/test_content_writer.py

import pytest
from unittest.mock import patch, AsyncMock

from app.core.content_writer import write_slide_content
from app.models.schema import SlideSpec, DeckPlan, SlideHTML

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_slide_spec():
    return SlideSpec(slide_id=1, title="Test Slide", key_points=["Point 1"])


@pytest.fixture
def mock_deck_plan():
    return DeckPlan(topic="Test Topic", audience="Test Audience", slides=[])


async def test_write_slide_content(mock_slide_spec, mock_deck_plan):
    """Test the write_slide_content function."""
    mock_result_html = SlideHTML(
        slide_id=1, template_name="test.html", html="<h1>Test Slide</h1>"
    )

    with patch("app.core.content_writer.build_renderer_chain") as mock_build_chain:
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = mock_result_html
        mock_build_chain.return_value = mock_chain

        slide_html = await write_slide_content(
            slide_spec=mock_slide_spec,
            deck_plan=mock_deck_plan,
            candidate_templates_html="<template></template>",
            model="test-model",
        )

        mock_build_chain.assert_called_once()
        mock_chain.ainvoke.assert_called_once()
        assert slide_html.slide_id == 1
        assert slide_html.html == "<h1>Test Slide</h1>"
