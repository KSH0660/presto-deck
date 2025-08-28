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
    from app.api.v1 import presentation
    presentation.slides_db.clear()
    presentation.next_slide_id = 1
    # A test function will be run at this point
    yield
    # Code that will run after each test
    presentation.slides_db.clear()
    presentation.next_slide_id = 1


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


async def test_get_slides_empty(client):
    """Test GET /slides when no slides exist."""
    response = await client.get("/api/v1/slides")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "No slides yet" in response.text


async def test_create_and_get_slides(client):
    """Test creating a slide and then getting the list of slides."""
    # Create a new slide
    response = await client.post(
        "/api/v1/slides/new",
        data={"title": "My First Slide", "html_content": "<p>Hello</p>"},
    )
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "My First Slide" in response.text
    assert "<p>Hello</p>" in response.text

    # Get the list of slides
    response = await client.get("/api/v1/slides")
    assert response.status_code == 200
    assert "My First Slide" in response.text
    assert "<p>Hello</p>" in response.text


async def test_edit_slide(client):
    """Test editing an existing slide."""
    # First, create a slide
    await client.post(
        "/api/v1/slides/new",
        data={"title": "Original Title", "html_content": "<p>Original</p>"},
    )

    # Mock the LLM chain
    with patch("langchain_openai.ChatOpenAI.ainvoke", new_callable=AsyncMock) as mock_ainvoke:
        mock_ainvoke.return_value = "<p>New AI-generated content</p>"

        # Now, edit the slide
        response = await client.post(
            "/api/v1/slides/1/edit",
            json={"edit_prompt": "Change the content"},
        )

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<p>New AI-generated content</p>" in response.text

    # Verify the mock was called
    mock_ainvoke.assert_called_once()


async def test_edit_slide_not_found(client):
    """Test editing a non-existent slide."""
    response = await client.post(
        "/api/v1/slides/999/edit",
        json={"edit_prompt": "This should fail"},
    )
    assert response.status_code == 404


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


async def test_export_html(client):
    """Test exporting slides to a single HTML file."""
    # Add a couple of slides
    await client.post(
        "/api/v1/slides/new",
        data={"title": "Slide 1", "html_content": "<h1>First</h1>"},
    )
    await client.post(
        "/api/v1/slides/new",
        data={"title": "Slide 2", "html_content": "<h2>Second</h2>"},
    )

    response = await client.get("/api/v1/export/html")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    html = response.text
    assert "<html>" in html
    assert "<h1>First</h1>" in html
    assert "<h2>Second</h2>" in html
    assert "</html>" in html


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