"""Comprehensive domain entity tests."""

from datetime import datetime, UTC, timedelta
from uuid import uuid4, UUID

from app.domain.entities import Deck, DeckStatus, Slide, DeckEvent


class TestDeck:
    """Test cases for Deck entity."""

    def test_deck_creation_with_defaults(self):
        """Test deck creation with default values."""
        deck = Deck(user_id="test-user", title="Test Deck")

        assert isinstance(deck.id, UUID)
        assert deck.user_id == "test-user"
        assert deck.title == "Test Deck"
        assert deck.status == DeckStatus.PENDING
        assert deck.version == 1
        assert deck.deck_plan is None
        assert isinstance(deck.created_at, datetime)
        assert isinstance(deck.updated_at, datetime)
        # created_at and updated_at should be very close (within 1 second)
        assert abs((deck.updated_at - deck.created_at).total_seconds()) < 1

    def test_deck_creation_with_custom_values(self):
        """Test deck creation with custom values."""
        custom_id = uuid4()
        custom_time = datetime.now(UTC)
        deck_plan = {"slides": [{"title": "Slide 1"}]}

        deck = Deck(
            id=custom_id,
            user_id="custom-user",
            title="Custom Deck",
            status=DeckStatus.COMPLETED,
            version=5,
            deck_plan=deck_plan,
            created_at=custom_time,
            updated_at=custom_time,
        )

        assert deck.id == custom_id
        assert deck.user_id == "custom-user"
        assert deck.title == "Custom Deck"
        assert deck.status == DeckStatus.COMPLETED
        assert deck.version == 5
        assert deck.deck_plan == deck_plan
        assert deck.created_at == custom_time
        assert deck.updated_at == custom_time

    def test_can_be_cancelled_states(self, sample_deck):
        """Test can_be_cancelled for various deck states."""
        # PENDING state
        sample_deck.status = DeckStatus.PENDING
        assert sample_deck.can_be_cancelled() is True

        # PLANNING state
        sample_deck.status = DeckStatus.PLANNING
        assert sample_deck.can_be_cancelled() is True

        # GENERATING state
        sample_deck.status = DeckStatus.GENERATING
        assert sample_deck.can_be_cancelled() is True

        # COMPLETED state
        sample_deck.status = DeckStatus.COMPLETED
        assert sample_deck.can_be_cancelled() is False

        # FAILED state
        sample_deck.status = DeckStatus.FAILED
        assert sample_deck.can_be_cancelled() is False

        # CANCELLED state
        sample_deck.status = DeckStatus.CANCELLED
        assert sample_deck.can_be_cancelled() is False

    def test_can_be_modified_states(self, sample_deck):
        """Test can_be_modified for various deck states."""
        # PENDING state
        sample_deck.status = DeckStatus.PENDING
        assert sample_deck.can_be_modified() is True

        # PLANNING state
        sample_deck.status = DeckStatus.PLANNING
        assert sample_deck.can_be_modified() is True

        # GENERATING state
        sample_deck.status = DeckStatus.GENERATING
        assert sample_deck.can_be_modified() is True

        # COMPLETED state
        sample_deck.status = DeckStatus.COMPLETED
        assert sample_deck.can_be_modified() is True

        # FAILED state
        sample_deck.status = DeckStatus.FAILED
        assert sample_deck.can_be_modified() is False

        # CANCELLED state
        sample_deck.status = DeckStatus.CANCELLED
        assert sample_deck.can_be_modified() is False

    def test_is_in_progress_states(self, sample_deck):
        """Test is_in_progress for various deck states."""
        # In progress states
        in_progress_states = [
            DeckStatus.PENDING,
            DeckStatus.PLANNING,
            DeckStatus.GENERATING,
        ]

        for status in in_progress_states:
            sample_deck.status = status
            assert sample_deck.is_in_progress() is True

        # Not in progress states
        not_in_progress_states = [
            DeckStatus.COMPLETED,
            DeckStatus.FAILED,
            DeckStatus.CANCELLED,
        ]

        for status in not_in_progress_states:
            sample_deck.status = status
            assert sample_deck.is_in_progress() is False

    def test_increment_version(self, sample_deck):
        """Test version increment functionality."""
        initial_version = sample_deck.version
        initial_updated_at = sample_deck.updated_at

        # Small delay to ensure timestamp difference
        import time

        time.sleep(0.001)

        sample_deck.increment_version()

        assert sample_deck.version == initial_version + 1
        assert sample_deck.updated_at > initial_updated_at

    def test_update_status(self, sample_deck):
        """Test status update functionality."""
        initial_version = sample_deck.version
        initial_updated_at = sample_deck.updated_at

        # Small delay to ensure timestamp difference
        import time

        time.sleep(0.001)

        sample_deck.update_status(DeckStatus.PLANNING)

        assert sample_deck.status == DeckStatus.PLANNING
        assert sample_deck.version == initial_version + 1
        assert sample_deck.updated_at > initial_updated_at

    def test_update_plan(self, sample_deck):
        """Test deck plan update functionality."""
        initial_version = sample_deck.version
        initial_updated_at = sample_deck.updated_at
        plan_data = {"slides": [{"title": "New Slide"}]}

        # Small delay to ensure timestamp difference
        import time

        time.sleep(0.001)

        sample_deck.update_plan(plan_data)

        assert sample_deck.deck_plan == plan_data
        assert sample_deck.version == initial_version + 1
        assert sample_deck.updated_at > initial_updated_at

    def test_deck_status_transitions(self, sample_deck):
        """Test valid deck status transitions."""
        # PENDING -> PLANNING
        sample_deck.status = DeckStatus.PENDING
        sample_deck.update_status(DeckStatus.PLANNING)
        assert sample_deck.status == DeckStatus.PLANNING

        # PLANNING -> GENERATING
        sample_deck.update_status(DeckStatus.GENERATING)
        assert sample_deck.status == DeckStatus.GENERATING

        # GENERATING -> COMPLETED
        sample_deck.update_status(DeckStatus.COMPLETED)
        assert sample_deck.status == DeckStatus.COMPLETED

    def test_deck_cancellation_workflow(self, sample_deck):
        """Test deck cancellation from various states."""
        cancellable_states = [
            DeckStatus.PENDING,
            DeckStatus.PLANNING,
            DeckStatus.GENERATING,
        ]

        for status in cancellable_states:
            sample_deck.status = status
            assert sample_deck.can_be_cancelled() is True

            sample_deck.update_status(DeckStatus.CANCELLED)
            assert sample_deck.status == DeckStatus.CANCELLED
            assert sample_deck.can_be_cancelled() is False

    def test_deck_equality_and_hash(self):
        """Test deck equality and hashing."""
        deck_id = uuid4()
        deck1 = Deck(id=deck_id, user_id="user1", title="Deck 1")
        deck2 = Deck(
            id=deck_id, user_id="user2", title="Deck 2"
        )  # Same ID, different data
        deck3 = Deck(
            id=uuid4(), user_id="user1", title="Deck 1"
        )  # Different ID, same data

        # Equality should be based on ID
        assert deck1 == deck2
        assert deck1 != deck3

        # Hash should be based on ID
        assert hash(deck1) == hash(deck2)
        assert hash(deck1) != hash(deck3)


class TestSlide:
    """Test cases for Slide entity."""

    def test_slide_creation_with_defaults(self, sample_deck):
        """Test slide creation with default values."""
        slide = Slide(
            deck_id=sample_deck.id, slide_order=1, html_content="<h1>Test</h1>"
        )

        assert isinstance(slide.id, UUID)
        assert slide.deck_id == sample_deck.id
        assert slide.slide_order == 1
        assert slide.html_content == "<h1>Test</h1>"
        assert slide.presenter_notes is None
        assert isinstance(slide.created_at, datetime)
        assert isinstance(slide.updated_at, datetime)
        assert slide.created_at == slide.updated_at

    def test_slide_creation_with_all_fields(self, sample_deck):
        """Test slide creation with all fields specified."""
        slide_id = uuid4()
        custom_time = datetime.now(UTC)

        slide = Slide(
            id=slide_id,
            deck_id=sample_deck.id,
            slide_order=3,
            html_content="<h1>Custom Slide</h1><p>Content</p>",
            presenter_notes="Custom presenter notes",
            created_at=custom_time,
            updated_at=custom_time,
        )

        assert slide.id == slide_id
        assert slide.deck_id == sample_deck.id
        assert slide.slide_order == 3
        assert slide.html_content == "<h1>Custom Slide</h1><p>Content</p>"
        assert slide.presenter_notes == "Custom presenter notes"
        assert slide.created_at == custom_time
        assert slide.updated_at == custom_time

    def test_update_content_with_notes(self, sample_slide):
        """Test updating slide content with presenter notes."""
        initial_updated_at = sample_slide.updated_at

        # Small delay to ensure timestamp difference
        import time

        time.sleep(0.001)

        new_content = "<h1>Updated Slide</h1><p>New content</p>"
        new_notes = "Updated presenter notes"

        sample_slide.update_content(new_content, new_notes)

        assert sample_slide.html_content == new_content
        assert sample_slide.presenter_notes == new_notes
        assert sample_slide.updated_at > initial_updated_at

    def test_update_content_without_notes(self, sample_slide):
        """Test updating slide content without changing presenter notes."""
        initial_notes = sample_slide.presenter_notes
        initial_updated_at = sample_slide.updated_at

        # Small delay to ensure timestamp difference
        import time

        time.sleep(0.001)

        new_content = "<h1>Updated Slide</h1><p>New content</p>"

        sample_slide.update_content(new_content, None)

        assert sample_slide.html_content == new_content
        assert sample_slide.presenter_notes == initial_notes
        assert sample_slide.updated_at > initial_updated_at

    def test_update_content_empty_notes(self, sample_slide):
        """Test updating slide content with empty notes."""
        initial_updated_at = sample_slide.updated_at

        # Small delay to ensure timestamp difference
        import time

        time.sleep(0.001)

        new_content = "<h1>Updated Slide</h1>"
        empty_notes = ""

        sample_slide.update_content(new_content, empty_notes)

        assert sample_slide.html_content == new_content
        assert sample_slide.presenter_notes == empty_notes
        assert sample_slide.updated_at > initial_updated_at

    def test_slide_ordering(self, sample_deck):
        """Test slide ordering functionality."""
        slides = []
        for i in range(5, 0, -1):  # Create in reverse order
            slide = Slide(
                deck_id=sample_deck.id,
                slide_order=i,
                html_content=f"<h1>Slide {i}</h1>",
            )
            slides.append(slide)

        # Sort by slide_order
        sorted_slides = sorted(slides, key=lambda s: s.slide_order)

        for i, slide in enumerate(sorted_slides, 1):
            assert slide.slide_order == i
            assert f"Slide {i}" in slide.html_content

    def test_slide_equality_and_hash(self, sample_deck):
        """Test slide equality and hashing."""
        slide_id = uuid4()
        slide1 = Slide(
            id=slide_id, deck_id=sample_deck.id, slide_order=1, html_content="Content 1"
        )
        slide2 = Slide(
            id=slide_id, deck_id=sample_deck.id, slide_order=2, html_content="Content 2"
        )
        slide3 = Slide(
            id=uuid4(), deck_id=sample_deck.id, slide_order=1, html_content="Content 1"
        )

        assert slide1 == slide2  # Same ID
        assert slide1 != slide3  # Different ID
        assert hash(slide1) == hash(slide2)
        assert hash(slide1) != hash(slide3)


class TestDeckEvent:
    """Test cases for DeckEvent entity."""

    def test_deck_event_creation_with_defaults(self, sample_deck):
        """Test deck event creation with default values."""
        event = DeckEvent(deck_id=sample_deck.id, version=1, event_type="DeckStarted")

        assert event.id is None  # ID set by database
        assert event.deck_id == sample_deck.id
        assert event.version == 1
        assert event.event_type == "DeckStarted"
        assert event.payload == {}
        assert isinstance(event.created_at, datetime)

    def test_deck_event_creation_with_payload(self, sample_deck):
        """Test deck event creation with payload."""
        payload = {"title": "Test Deck", "slide_count": 5, "user_action": "create"}

        event = DeckEvent(
            deck_id=sample_deck.id, version=2, event_type="SlideAdded", payload=payload
        )

        assert event.deck_id == sample_deck.id
        assert event.version == 2
        assert event.event_type == "SlideAdded"
        assert event.payload == payload

    def test_deck_event_with_custom_timestamp(self, sample_deck):
        """Test deck event creation with custom timestamp."""
        custom_time = datetime.now(UTC) - timedelta(hours=1)

        event = DeckEvent(
            deck_id=sample_deck.id,
            version=1,
            event_type="DeckCompleted",
            created_at=custom_time,
        )

        assert event.created_at == custom_time

    def test_deck_event_types(self, sample_deck):
        """Test various deck event types."""
        event_types = [
            "DeckStarted",
            "PlanUpdated",
            "SlideAdded",
            "SlideUpdated",
            "DeckCompleted",
            "DeckFailed",
            "DeckCancelled",
            "Heartbeat",
        ]

        for i, event_type in enumerate(event_types, 1):
            event = DeckEvent(deck_id=sample_deck.id, version=i, event_type=event_type)
            assert event.event_type == event_type
            assert event.version == i

    def test_deck_event_payload_types(self, sample_deck):
        """Test deck event with various payload types."""
        payloads = [
            {},  # Empty dict
            {"simple": "value"},  # Simple dict
            {"nested": {"key": "value"}},  # Nested dict
            {"list": [1, 2, 3]},  # List in dict
            {
                "mixed": {"string": "value", "number": 42, "boolean": True}
            },  # Mixed types
        ]

        for i, payload in enumerate(payloads, 1):
            event = DeckEvent(
                deck_id=sample_deck.id,
                version=i,
                event_type="TestEvent",
                payload=payload,
            )
            assert event.payload == payload

    def test_deck_event_version_ordering(self, sample_deck):
        """Test deck event version ordering."""
        events = []
        for version in [3, 1, 5, 2, 4]:  # Create in random order
            event = DeckEvent(
                deck_id=sample_deck.id, version=version, event_type=f"Event{version}"
            )
            events.append(event)

        # Sort by version
        sorted_events = sorted(events, key=lambda e: e.version)

        for i, event in enumerate(sorted_events, 1):
            assert event.version == i
            assert event.event_type == f"Event{i}"


class TestDeckStatusEnum:
    """Test cases for DeckStatus enum."""

    def test_deck_status_values(self):
        """Test deck status enum values."""
        assert DeckStatus.PENDING.value == "PENDING"
        assert DeckStatus.PLANNING.value == "PLANNING"
        assert DeckStatus.GENERATING.value == "GENERATING"
        assert DeckStatus.COMPLETED.value == "COMPLETED"
        assert DeckStatus.FAILED.value == "FAILED"
        assert DeckStatus.CANCELLED.value == "CANCELLED"

    def test_deck_status_equality(self):
        """Test deck status equality."""
        assert DeckStatus.PENDING == DeckStatus.PENDING
        assert DeckStatus.PENDING != DeckStatus.COMPLETED
        assert DeckStatus("PENDING") == DeckStatus.PENDING

    def test_deck_status_string_representation(self):
        """Test deck status string representation."""
        assert str(DeckStatus.PENDING) == "DeckStatus.PENDING"
        assert repr(DeckStatus.PENDING) == "<DeckStatus.PENDING: 'PENDING'>"

    def test_deck_status_iteration(self):
        """Test iterating over deck status values."""
        statuses = list(DeckStatus)
        expected = [
            DeckStatus.PENDING,
            DeckStatus.PLANNING,
            DeckStatus.GENERATING,
            DeckStatus.COMPLETED,
            DeckStatus.FAILED,
            DeckStatus.CANCELLED,
        ]
        assert statuses == expected

    def test_deck_status_membership(self):
        """Test deck status membership testing."""
        assert "PENDING" in [status.value for status in DeckStatus]
        assert "INVALID" not in [status.value for status in DeckStatus]


class TestEntityValidation:
    """Test cases for entity validation and edge cases."""

    def test_deck_with_empty_title(self):
        """Test deck creation with empty title."""
        # This should be handled by validation layer, not domain entity
        deck = Deck(user_id="user", title="")
        assert deck.title == ""

    def test_deck_with_very_long_title(self):
        """Test deck with very long title."""
        long_title = "A" * 1000
        deck = Deck(user_id="user", title=long_title)
        assert deck.title == long_title

    def test_slide_with_empty_html_content(self, sample_deck):
        """Test slide with empty HTML content."""
        slide = Slide(deck_id=sample_deck.id, slide_order=1, html_content="")
        assert slide.html_content == ""

    def test_slide_with_negative_order(self, sample_deck):
        """Test slide with negative order."""
        slide = Slide(
            deck_id=sample_deck.id, slide_order=-1, html_content="<h1>Test</h1>"
        )
        assert slide.slide_order == -1

    def test_event_with_empty_event_type(self, sample_deck):
        """Test event with empty event type."""
        event = DeckEvent(deck_id=sample_deck.id, version=1, event_type="")
        assert event.event_type == ""

    def test_event_with_zero_version(self, sample_deck):
        """Test event with zero version."""
        event = DeckEvent(deck_id=sample_deck.id, version=0, event_type="TestEvent")
        assert event.version == 0


class TestEntitySerializationAndCopy:
    """Test entity serialization and copying behavior."""

    def test_deck_dict_conversion(self, sample_deck):
        """Test deck to dict conversion."""
        deck_dict = sample_deck.model_dump()

        assert deck_dict["id"] == sample_deck.id
        assert deck_dict["user_id"] == sample_deck.user_id
        assert deck_dict["title"] == sample_deck.title
        assert deck_dict["status"] == sample_deck.status
        assert deck_dict["version"] == sample_deck.version

    def test_deck_json_conversion(self, sample_deck):
        """Test deck JSON serialization."""
        json_str = sample_deck.model_dump_json()
        assert isinstance(json_str, str)
        assert sample_deck.user_id in json_str
        assert sample_deck.title in json_str

    def test_deck_copy(self, sample_deck):
        """Test deck copying."""
        deck_copy = sample_deck.model_copy()

        assert deck_copy.id == sample_deck.id
        assert deck_copy.user_id == sample_deck.user_id
        assert deck_copy is not sample_deck  # Different instances

    def test_deck_copy_with_updates(self, sample_deck):
        """Test deck copying with field updates."""
        deck_copy = sample_deck.model_copy(update={"title": "Updated Title"})

        assert deck_copy.title == "Updated Title"
        assert deck_copy.user_id == sample_deck.user_id
        assert deck_copy.id == sample_deck.id
