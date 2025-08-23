#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This file contains unit tests.

Unit tests focus on testing individual functions (units) in isolation
to ensure they work correctly.
"""

import pytest
from unittest.mock import patch, AsyncMock

# The function to be tested
from presto.app.api.v1.generate import generate_slide_html


@pytest.mark.asyncio
async def test_generate_slide_html():
    """Unit test for the generate_slide_html function."""
    # 1. Arrange: Prepare the test data and mock.
    # We need sample input data for our function.
    sample_slide_data = {"title": "Test Title", "content": ["Point 1", "Point 2"]}
    # This is the fake HTML response we want our mock to return.
    expected_html = "<h1>Test Title</h1><ul><li>Point 1</li><li>Point 2</li></ul>"

    # Patch the function that our unit depends on. `generate_slide_html` calls
    # `generate_content_openai`, so we replace it with a mock.
    with patch(
        "presto.app.api.v1.generate.generate_content_openai", new_callable=AsyncMock
    ) as mock_llm_call:
        # Configure the mock to return our fake HTML.
        mock_llm_call.return_value = expected_html

        # 2. Act: Call the function we are testing.
        actual_html = await generate_slide_html(sample_slide_data, model="gpt-4o-mini")

        # 3. Assert: Verify the results.
        # Check that the function returned the HTML from our mock.
        assert actual_html == expected_html

        # Check that our function called the LLM with the correct parameters.
        mock_llm_call.assert_called_once()
        call_args = mock_llm_call.call_args
        # Verify the prompt sent to the LLM is correct.
        assert "Test Title" in call_args.args[0]
        assert "Point 1\n- Point 2" in call_args.args[0]
        # Verify the model name is passed correctly.
        assert call_args.kwargs["model"] == "gpt-4o-mini"
