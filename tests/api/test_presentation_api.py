# tests/api/test_presentation_api.py
import json
import pytest
from unittest.mock import patch, AsyncMock

from app.models.schema import DeckPlan, SlideSpec, SlideHTML

# Mark all tests in this file as asyncio tests
pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def run_around_tests():
    # Code that will run before each test
    from app.core import state

    state.slides_db.clear()
    state.next_slide_id = 1
    # A test function will be run at this point
    yield
    # Code that will run after each test
    state.slides_db.clear()
    state.next_slide_id = 1


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


async def test_edit_slide(client, monkeypatch):
    """Test editing an existing slide."""
    # Setup: Directly manipulate the in-memory DB for the test
    initial_slide = {
        "id": 1,
        "title": "Original Title",
        "html_content": "<p>Original</p>",
        "version": 1,
    }

    # Import the state module to access slides_db
    from app.core import state

    monkeypatch.setattr(state, "slides_db", [initial_slide])
    monkeypatch.setattr(state, "next_slide_id", 2)

    # Mock the core edit function for a more robust unit test
    with patch(
        "app.api.v1.presentation.edit_slide_content", new_callable=AsyncMock
    ) as mock_edit_content:
        mock_edit_content.return_value = "<p>New AI-generated content</p>"

        # Now, edit the slide
        response = await client.post(
            "/api/v1/slides/1/edit",
            json={"edit_prompt": "Change the content"},
        )

    assert response.status_code == 200
    response_json = response.json()
    assert response_json["id"] == 1
    assert response_json["html_content"] == "<p>New AI-generated content</p>"
    assert response_json["version"] == 2  # Incremented from 1

    # Verify the mock was called correctly
    mock_edit_content.assert_called_once_with(
        original_html="<p>Original</p>", edit_prompt="Change the content"
    )


async def test_add_slide(client):
    """Test adding a new slide."""
    # Mock the core add function
    with patch(
        "app.api.v1.presentation.add_slide_content", new_callable=AsyncMock
    ) as mock_add_content:
        mock_add_content.return_value = {
            "title": "Added Slide",
            "html_content": "<h1>Added Content</h1>",
        }

        response = await client.post(
            "/api/v1/slides/add",
            json={"add_prompt": "A slide about testing"},
        )

    assert response.status_code == 201
    response_json = response.json()
    assert response_json["id"] == 1
    assert response_json["title"] == "Added Slide"
    assert response_json["html_content"] == "<h1>Added Content</h1>"
    assert response_json["version"] == 1

    # Check if it was actually added to the db
    from app.core import state

    assert len(state.slides_db) == 1
    assert state.slides_db[0]["id"] == 1
    assert state.slides_db[0]["title"] == "Added Slide"

    mock_add_content.assert_called_once_with("A slide about testing")


async def test_get_progress_stream(client):
    """Test the /progress SSE endpoint."""
    response = await client.get("/api/v1/progress")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    events = []
    async for line in response.aiter_lines():
        if line.startswith("data:"):
            events.append(line.split(":", 1)[1].strip())

    assert events == ["Planning", "Selecting Templates", "Rendering Slides", "Complete"]


async def test_generate_presentation_streams_events(client, mock_deck_plan):
    """Test that the /generate endpoint streams SSE events correctly."""
    plan_with_candidates = mock_deck_plan.model_copy(deep=True)
    plan_with_candidates.slides[0].layout_candidates = ["title.html"]
    plan_with_candidates.slides[1].layout_candidates = ["content.html"]

    with (
        patch(
            "app.core.streaming.planner.plan_deck", new_callable=AsyncMock
        ) as mock_plan,
        patch(
            "app.core.streaming.layout_selector.run_layout_selection_for_deck",
            new_callable=AsyncMock,
        ) as mock_run_layout,
        patch(
            "app.core.streaming.slide_worker.process_slide", new_callable=AsyncMock
        ) as mock_process,
    ):
        # Configure mock return values
        mock_plan.return_value = mock_deck_plan
        mock_run_layout.return_value = plan_with_candidates
        mock_process.side_effect = [
            SlideHTML(slide_id=1, template_name="title.html", html="<h1>Slide 1</h1>"),
            SlideHTML(slide_id=2, template_name="content.html", html="<p>Slide 2</p>"),
        ]

        # Make the API call
        response = await client.post(
            "/api/v1/generate",
            json={"user_prompt": "Test presentation", "config": {"quality": "default"}},
        )

        # Assertions for the response itself
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        # Process the stream
        events = []
        current_event = None
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
            if line.startswith("data:"):
                data = json.loads(line.split(":", 1)[1].strip())
                events.append({"event": current_event, "data": data})

        # Verify the events were received as expected
        event_types = [e["event"] for e in events]
        assert "started" in event_types
        assert "deck_plan" in event_types
        assert event_types.count("slide_rendered") == 2
        assert "completed" in event_types

        # Verify content of specific events
        deck_plan_event = next(e for e in events if e["event"] == "deck_plan")
        assert deck_plan_event["data"]["topic"] == "Test Topic"
        assert len(deck_plan_event["data"]["slides"]) == 2

        first_slide_event = next(
            e
            for e in events
            if e["event"] == "slide_rendered" and e["data"]["slide_id"] == 1
        )
        assert first_slide_event["data"]["html"] == "<h1>Slide 1</h1>"

        second_slide_event = next(
            e
            for e in events
            if e["event"] == "slide_rendered" and e["data"]["slide_id"] == 2
        )
        assert second_slide_event["data"]["html"] == "<p>Slide 2</p>"

        # Assert that our mocks were called correctly
        mock_plan.assert_called_once()
        mock_run_layout.assert_called_once()
        assert mock_process.call_count == 2
