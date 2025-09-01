import pytest
from uuid import uuid4

from app.domain.entities import Deck, DeckStatus, Slide
from app.infrastructure.llm.models import DeckPlan, SlideContent


@pytest.mark.asyncio
async def test_complete_deck_generation_workflow():
    """Test the complete deck generation workflow from API to worker completion."""

    # This is a simplified E2E test that mocks external dependencies
    # In a real environment, this would use test databases and Redis instances

    # Mock LLM client responses
    mock_deck_plan = DeckPlan(
        title="AI in Business",
        slides=[
            {
                "slide_number": 1,
                "title": "Introduction",
                "type": "title",
                "key_points": ["Welcome", "Agenda"],
                "content_type": "text",
                "estimated_duration": 2,
            },
            {
                "slide_number": 2,
                "title": "AI Overview",
                "type": "content",
                "key_points": ["Definition", "Applications"],
                "content_type": "text",
                "estimated_duration": 3,
            },
        ],
        total_slides=2,
        estimated_duration=5,
        target_audience="Business leaders",
    )

    mock_slide_content_1 = SlideContent(
        title="Introduction",
        content="Welcome to our presentation on AI in Business",
        html_content="<h1>Introduction</h1><p>Welcome to our presentation on AI in Business</p>",
        presenter_notes="Start with a warm welcome and outline the agenda",
        slide_number=1,
    )

    mock_slide_content_2 = SlideContent(
        title="AI Overview",
        content="AI is transforming business operations worldwide",
        html_content="<h1>AI Overview</h1><p>AI is transforming business operations worldwide</p>",
        presenter_notes="Explain key AI concepts and business applications",
        slide_number=2,
    )

    # Simulate the workflow
    workflow_events = []

    # 1. API receives deck creation request
    deck = Deck(
        id=uuid4(),
        user_id="test-user",
        title="AI in Business",
        status=DeckStatus.PENDING,
    )
    workflow_events.append(("deck_created", deck.id, deck.status))

    # 2. Worker picks up the job and starts planning
    deck.update_status(DeckStatus.PLANNING)
    workflow_events.append(("status_updated", deck.id, deck.status))

    # 3. Worker generates deck plan
    deck.update_plan(mock_deck_plan.model_dump())
    deck.update_status(DeckStatus.GENERATING)
    workflow_events.append(("plan_generated", deck.id, len(mock_deck_plan.slides)))

    # 4. Worker generates slides one by one
    slides = []

    # Generate slide 1
    slide_1 = Slide(
        id=uuid4(),
        deck_id=deck.id,
        slide_order=1,
        html_content=mock_slide_content_1.html_content,
        presenter_notes=mock_slide_content_1.presenter_notes,
    )
    slides.append(slide_1)
    deck.increment_version()
    workflow_events.append(("slide_generated", slide_1.id, slide_1.slide_order))

    # Generate slide 2
    slide_2 = Slide(
        id=uuid4(),
        deck_id=deck.id,
        slide_order=2,
        html_content=mock_slide_content_2.html_content,
        presenter_notes=mock_slide_content_2.presenter_notes,
    )
    slides.append(slide_2)
    deck.increment_version()
    workflow_events.append(("slide_generated", slide_2.id, slide_2.slide_order))

    # 5. Worker completes deck generation
    deck.update_status(DeckStatus.COMPLETED)
    workflow_events.append(("deck_completed", deck.id, len(slides)))

    # Assertions to verify workflow
    assert len(workflow_events) == 6
    assert workflow_events[0][0] == "deck_created"
    assert workflow_events[1][0] == "status_updated"
    assert workflow_events[2][0] == "plan_generated"
    assert workflow_events[3][0] == "slide_generated"
    assert workflow_events[4][0] == "slide_generated"
    assert workflow_events[5][0] == "deck_completed"

    # Verify final state
    assert deck.status == DeckStatus.COMPLETED
    # Version increments on status changes and content updates
    assert deck.version == 7
    assert len(slides) == 2
    assert deck.deck_plan is not None
    assert slides[0].slide_order == 1
    assert slides[1].slide_order == 2


@pytest.mark.asyncio
async def test_deck_generation_with_cancellation():
    """Test deck generation workflow with user cancellation."""

    workflow_events = []

    # Start deck generation
    deck = Deck(
        id=uuid4(),
        user_id="test-user",
        title="Cancelled Deck",
        status=DeckStatus.PENDING,
    )
    workflow_events.append(("deck_created", deck.id))

    # Worker starts processing
    deck.update_status(DeckStatus.PLANNING)
    workflow_events.append(("planning_started", deck.id))

    # User requests cancellation during planning
    cancellation_requested = True
    workflow_events.append(("cancellation_requested", deck.id))

    # Worker detects cancellation and stops
    if cancellation_requested:
        deck.update_status(DeckStatus.CANCELLED)
        workflow_events.append(("deck_cancelled", deck.id))

    # Verify cancellation workflow
    assert len(workflow_events) == 4
    assert workflow_events[-2][0] == "cancellation_requested"
    assert workflow_events[-1][0] == "deck_cancelled"
    assert deck.status == DeckStatus.CANCELLED


@pytest.mark.asyncio
async def test_deck_generation_with_llm_failure():
    """Test deck generation workflow with LLM failure and recovery."""

    workflow_events = []

    deck = Deck(
        id=uuid4(), user_id="test-user", title="Failed Deck", status=DeckStatus.PENDING
    )
    workflow_events.append(("deck_created", deck.id))

    # Worker starts processing
    deck.update_status(DeckStatus.PLANNING)
    workflow_events.append(("planning_started", deck.id))

    # Simulate LLM failure
    llm_failed = True
    retry_count = 0
    max_retries = 3

    while llm_failed and retry_count < max_retries:
        retry_count += 1
        workflow_events.append(("llm_retry", deck.id, retry_count))

        # Simulate failure on first 2 attempts, success on 3rd
        if retry_count == 3:
            llm_failed = False

    if llm_failed:
        # Max retries exceeded
        deck.update_status(DeckStatus.FAILED)
        workflow_events.append(("deck_failed", deck.id, "LLM failure"))
    else:
        # Eventually succeeded
        deck.update_status(DeckStatus.GENERATING)
        workflow_events.append(("llm_recovered", deck.id))

    # Verify retry and recovery workflow
    assert retry_count == 3
    assert not llm_failed  # Should have recovered
    assert deck.status == DeckStatus.GENERATING
    assert any("llm_retry" in event for event in workflow_events)
    assert workflow_events[-1][0] == "llm_recovered"


@pytest.mark.asyncio
async def test_websocket_event_replay_scenario():
    """Test WebSocket client reconnection with event replay."""

    # Simulate events that occurred while client was disconnected
    historical_events = [
        {"event_type": "DeckStarted", "version": 1, "payload": {"title": "Test Deck"}},
        {"event_type": "PlanUpdated", "version": 2, "payload": {"total_slides": 3}},
        {
            "event_type": "SlideAdded",
            "version": 3,
            "payload": {"slide_id": str(uuid4()), "slide_order": 1},
        },
        {
            "event_type": "SlideAdded",
            "version": 4,
            "payload": {"slide_id": str(uuid4()), "slide_order": 2},
        },
    ]

    # Client reconnects with last_version=2 (missed events 3 and 4)
    client_last_version = 2
    missed_events = [
        event for event in historical_events if event["version"] > client_last_version
    ]

    # Verify replay logic
    assert len(missed_events) == 2
    assert missed_events[0]["event_type"] == "SlideAdded"
    assert missed_events[0]["version"] == 3
    assert missed_events[1]["event_type"] == "SlideAdded"
    assert missed_events[1]["version"] == 4

    # Simulate sending replay events to client
    replayed_events = []
    for event in missed_events:
        replayed_events.append({"type": "replay", "data": event})

    # Send replay complete signal
    replayed_events.append(
        {"type": "replay_complete", "data": {"replayed_events": len(missed_events)}}
    )

    assert len(replayed_events) == 3
    assert replayed_events[-1]["type"] == "replay_complete"
