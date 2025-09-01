"""Comprehensive application services unit tests."""

import pytest
from unittest.mock import AsyncMock, Mock, patch, call
from uuid import uuid4
from typing import Dict, Any

from app.application.services import DeckService, SlideService
from app.domain.entities import Deck, DeckStatus, Slide, DeckEvent
from app.domain.exceptions import (
    DeckNotFoundException,
    UnauthorizedAccessException,
    InvalidDeckStatusException,
)
from app.api.schemas import DeckCreationRequest
from tests._helpers.fakes import (
    FakeDeckRepository,
    FakeSlideRepository,
    FakeEventRepository,
)


class TestDeckService:
    """Test cases for DeckService."""

    @pytest.fixture
    def deck_service(self, mock_stream_publisher, mock_cache_manager, mock_arq_redis):
        """Create DeckService with mocked dependencies."""
        deck_repo = FakeDeckRepository()
        slide_repo = FakeSlideRepository()
        event_repo = FakeEventRepository()
        
        return DeckService(
            deck_repo=deck_repo,
            slide_repo=slide_repo,
            event_repo=event_repo,
            stream_publisher=mock_stream_publisher,
            cache_manager=mock_cache_manager,
            arq_redis=mock_arq_redis,
        )

    @pytest.mark.asyncio
    async def test_create_deck_success(self, deck_service, deck_creation_request, test_user_id):
        """Test successful deck creation."""
        request = DeckCreationRequest(**deck_creation_request)
        
        deck = await deck_service.create_deck(request, test_user_id)
        
        # Verify deck properties
        assert deck.user_id == test_user_id
        assert deck.title == request.title
        assert deck.status == DeckStatus.PENDING
        assert deck.version == 1
        
        # Verify deck was saved
        assert await deck_service.deck_repo.exists(deck.id)
        
        # Verify event was created and published
        events = deck_service.event_repo.events
        assert len(events) == 1
        assert events[0].event_type == "DeckStarted"
        assert events[0].deck_id == deck.id
        
        # Verify job was enqueued
        deck_service.arq_redis.enqueue_job.assert_called_once_with(
            "generate_deck",
            deck_id=str(deck.id),
            generation_params={
                "title": request.title,
                "topic": request.topic,
                "audience": request.audience,
                "style": request.style,
                "slide_count": request.slide_count,
                "language": request.language,
                "include_speaker_notes": request.include_speaker_notes,
            }
        )
        
        # Verify event was published
        deck_service.stream_publisher.publish_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_deck_with_minimal_request(self, deck_service, test_user_id):
        """Test deck creation with minimal request data."""
        minimal_request = DeckCreationRequest(
            title="Minimal Deck",
            topic="Basic Topic"
        )
        
        deck = await deck_service.create_deck(minimal_request, test_user_id)
        
        assert deck.title == "Minimal Deck"
        assert deck.user_id == test_user_id
        assert deck.status == DeckStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_deck_success(self, deck_service, sample_deck, test_user_id):
        """Test successful deck retrieval."""
        # Add deck to repository
        await deck_service.deck_repo.create(sample_deck)
        
        retrieved_deck = await deck_service.get_deck(sample_deck.id, test_user_id)
        
        assert retrieved_deck.id == sample_deck.id
        assert retrieved_deck.title == sample_deck.title

    @pytest.mark.asyncio
    async def test_get_deck_not_found(self, deck_service, test_user_id):
        """Test deck retrieval when deck doesn't exist."""
        fake_deck_id = uuid4()
        
        with pytest.raises(DeckNotFoundException):
            await deck_service.get_deck(fake_deck_id, test_user_id)

    @pytest.mark.asyncio
    async def test_get_deck_unauthorized(self, deck_service, sample_deck, another_user_id):
        """Test deck retrieval with unauthorized access."""
        # Add deck to repository (owned by test_user_id)
        await deck_service.deck_repo.create(sample_deck)
        
        with pytest.raises(UnauthorizedAccessException):
            await deck_service.get_deck(sample_deck.id, another_user_id)

    @pytest.mark.asyncio
    async def test_get_deck_with_slides(self, deck_service, sample_deck, test_user_id):
        """Test deck retrieval with slides."""
        # Add deck and slides to repositories
        await deck_service.deck_repo.create(sample_deck)
        
        slides = []
        for i in range(3):
            slide = Slide(
                deck_id=sample_deck.id,
                slide_order=i + 1,
                html_content=f"<h1>Slide {i + 1}</h1>"
            )
            await deck_service.slide_repo.create(slide)
            slides.append(slide)
        
        deck, retrieved_slides = await deck_service.get_deck_with_slides(sample_deck.id, test_user_id)
        
        assert deck.id == sample_deck.id
        assert len(retrieved_slides) == 3
        assert all(slide.deck_id == sample_deck.id for slide in retrieved_slides)
        # Verify slides are ordered
        assert retrieved_slides[0].slide_order == 1
        assert retrieved_slides[1].slide_order == 2
        assert retrieved_slides[2].slide_order == 3

    @pytest.mark.asyncio
    async def test_list_decks(self, deck_service, test_user_id):
        """Test listing user's decks."""
        # Create multiple decks for the user
        decks = []
        for i in range(5):
            deck = Deck(
                user_id=test_user_id,
                title=f"Deck {i + 1}"
            )
            await deck_service.deck_repo.create(deck)
            decks.append(deck)
        
        # Create deck for different user
        other_deck = Deck(
            user_id="other-user",
            title="Other User's Deck"
        )
        await deck_service.deck_repo.create(other_deck)
        
        # List decks for test user
        user_decks = await deck_service.list_decks(test_user_id)
        
        assert len(user_decks) == 5
        assert all(deck.user_id == test_user_id for deck in user_decks)
        assert not any(deck.user_id == "other-user" for deck in user_decks)

    @pytest.mark.asyncio
    async def test_list_decks_with_pagination(self, deck_service, test_user_id):
        """Test listing decks with pagination."""
        # Create 10 decks
        for i in range(10):
            deck = Deck(
                user_id=test_user_id,
                title=f"Deck {i + 1}"
            )
            await deck_service.deck_repo.create(deck)
        
        # Test pagination
        page1 = await deck_service.list_decks(test_user_id, limit=3, offset=0)
        page2 = await deck_service.list_decks(test_user_id, limit=3, offset=3)
        
        assert len(page1) == 3
        assert len(page2) == 3
        
        # Verify no overlap
        page1_ids = {deck.id for deck in page1}
        page2_ids = {deck.id for deck in page2}
        assert page1_ids.isdisjoint(page2_ids)

    @pytest.mark.asyncio
    async def test_cancel_deck_generation_success(self, deck_service, sample_deck, test_user_id):
        """Test successful deck generation cancellation."""
        # Set deck to GENERATING status
        sample_deck.status = DeckStatus.GENERATING
        await deck_service.deck_repo.create(sample_deck)
        
        updated_deck = await deck_service.cancel_deck_generation(sample_deck.id, test_user_id)
        
        assert updated_deck.status == DeckStatus.CANCELLED
        
        # Verify cancellation flag was set
        deck_service.cache_manager.set_cancellation_flag.assert_called_once_with(sample_deck.id)
        
        # Verify event was created and published
        events = deck_service.event_repo.events
        assert len(events) == 1
        assert events[0].event_type == "DeckCancelled"
        assert events[0].deck_id == sample_deck.id

    @pytest.mark.asyncio
    async def test_cancel_deck_invalid_status(self, deck_service, sample_deck, test_user_id):
        """Test cancellation of deck with invalid status."""
        # Set deck to COMPLETED status (not cancellable)
        sample_deck.status = DeckStatus.COMPLETED
        await deck_service.deck_repo.create(sample_deck)
        
        with pytest.raises(InvalidDeckStatusException):
            await deck_service.cancel_deck_generation(sample_deck.id, test_user_id)

    @pytest.mark.asyncio
    async def test_cancel_deck_not_found(self, deck_service, test_user_id):
        """Test cancellation of non-existent deck."""
        fake_deck_id = uuid4()
        
        with pytest.raises(DeckNotFoundException):
            await deck_service.cancel_deck_generation(fake_deck_id, test_user_id)

    @pytest.mark.asyncio
    async def test_cancel_deck_unauthorized(self, deck_service, sample_deck, another_user_id):
        """Test unauthorized deck cancellation."""
        await deck_service.deck_repo.create(sample_deck)
        
        with pytest.raises(UnauthorizedAccessException):
            await deck_service.cancel_deck_generation(sample_deck.id, another_user_id)

    @pytest.mark.asyncio
    async def test_get_deck_events(self, deck_service, sample_deck, test_user_id):
        """Test retrieving deck events."""
        await deck_service.deck_repo.create(sample_deck)
        
        # Create multiple events
        events = []
        for i in range(5):
            event = DeckEvent(
                deck_id=sample_deck.id,
                version=i + 1,
                event_type=f"Event{i + 1}",
                payload={"step": i + 1}
            )
            await deck_service.event_repo.create(event)
            events.append(event)
        
        # Get all events
        retrieved_events = await deck_service.get_deck_events(sample_deck.id, test_user_id)
        
        assert len(retrieved_events) == 5
        assert all(event.deck_id == sample_deck.id for event in retrieved_events)
        
        # Get events from specific version
        recent_events = await deck_service.get_deck_events(sample_deck.id, test_user_id, from_version=3)
        
        assert len(recent_events) == 2
        assert recent_events[0].version == 4
        assert recent_events[1].version == 5

    @pytest.mark.asyncio
    async def test_get_deck_events_unauthorized(self, deck_service, sample_deck, another_user_id):
        """Test unauthorized access to deck events."""
        await deck_service.deck_repo.create(sample_deck)
        
        with pytest.raises(UnauthorizedAccessException):
            await deck_service.get_deck_events(sample_deck.id, another_user_id)

    @pytest.mark.asyncio
    async def test_publish_event_error_handling(self, deck_service, sample_deck, test_user_id):
        """Test error handling when event publishing fails."""
        # Mock stream publisher to raise exception
        deck_service.stream_publisher.publish_event.side_effect = Exception("Redis error")
        
        # Should not raise exception (error should be logged but not propagated)
        deck = await deck_service.create_deck(
            DeckCreationRequest(title="Test", topic="Test topic for error handling"), 
            test_user_id
        )
        
        # Deck should still be created despite publishing failure
        assert deck.title == "Test"


class TestSlideService:
    """Test cases for SlideService."""

    @pytest.fixture
    def slide_service(self, mock_stream_publisher, mock_arq_redis):
        """Create SlideService with mocked dependencies."""
        slide_repo = FakeSlideRepository()
        deck_repo = FakeDeckRepository()
        event_repo = FakeEventRepository()
        
        return SlideService(
            slide_repo=slide_repo,
            deck_repo=deck_repo,
            event_repo=event_repo,
            stream_publisher=mock_stream_publisher,
            arq_redis=mock_arq_redis,
        )

    @pytest.mark.asyncio
    async def test_get_slide_success(self, slide_service, sample_deck, sample_slide, test_user_id):
        """Test successful slide retrieval."""
        # Add deck and slide to repositories
        await slide_service.deck_repo.create(sample_deck)
        await slide_service.slide_repo.create(sample_slide)
        
        retrieved_slide = await slide_service.get_slide(sample_slide.id, test_user_id)
        
        assert retrieved_slide.id == sample_slide.id
        assert retrieved_slide.html_content == sample_slide.html_content

    @pytest.mark.asyncio
    async def test_get_slide_not_found(self, slide_service, test_user_id):
        """Test slide retrieval when slide doesn't exist."""
        fake_slide_id = uuid4()
        
        with pytest.raises(DeckNotFoundException):
            await slide_service.get_slide(fake_slide_id, test_user_id)

    @pytest.mark.asyncio
    async def test_get_slide_unauthorized(self, slide_service, sample_deck, sample_slide, another_user_id):
        """Test unauthorized slide access."""
        # Add deck (owned by test_user_id) and slide to repositories
        await slide_service.deck_repo.create(sample_deck)
        await slide_service.slide_repo.create(sample_slide)
        
        with pytest.raises(UnauthorizedAccessException):
            await slide_service.get_slide(sample_slide.id, another_user_id)

    @pytest.mark.asyncio
    async def test_update_slide_success(self, slide_service, completed_deck, sample_slide, test_user_id):
        """Test successful slide update request."""
        # Add deck (COMPLETED status allows modifications) and slide
        await slide_service.deck_repo.create(completed_deck)
        sample_slide.deck_id = completed_deck.id
        await slide_service.slide_repo.create(sample_slide)
        
        prompt = "Make this slide more engaging"
        
        await slide_service.update_slide(sample_slide.id, prompt, test_user_id)
        
        # Verify job was enqueued
        slide_service.arq_redis.enqueue_job.assert_called_once_with(
            "update_slide",
            slide_id=str(sample_slide.id),
            update_prompt=prompt,
            user_id=test_user_id
        )

    @pytest.mark.asyncio
    async def test_update_slide_invalid_deck_status(self, slide_service, sample_deck, sample_slide, test_user_id):
        """Test slide update with deck in invalid status."""
        # Set deck to FAILED status (not modifiable)
        sample_deck.status = DeckStatus.FAILED
        await slide_service.deck_repo.create(sample_deck)
        await slide_service.slide_repo.create(sample_slide)
        
        with pytest.raises(InvalidDeckStatusException):
            await slide_service.update_slide(sample_slide.id, "Update prompt", test_user_id)

    @pytest.mark.asyncio
    async def test_add_slide_success(self, slide_service, completed_deck, test_user_id):
        """Test successful slide addition request."""
        await slide_service.deck_repo.create(completed_deck)
        
        position = 3
        prompt = "Add a new slide about conclusions"
        
        await slide_service.add_slide(completed_deck.id, position, prompt, test_user_id)
        
        # Verify job was enqueued
        slide_service.arq_redis.enqueue_job.assert_called_once_with(
            "add_slide",
            deck_id=str(completed_deck.id),
            position=position,
            prompt=prompt,
            user_id=test_user_id
        )

    @pytest.mark.asyncio
    async def test_add_slide_unauthorized(self, slide_service, completed_deck, another_user_id):
        """Test unauthorized slide addition."""
        await slide_service.deck_repo.create(completed_deck)
        
        with pytest.raises(UnauthorizedAccessException):
            await slide_service.add_slide(completed_deck.id, 1, "Prompt", another_user_id)

    @pytest.mark.asyncio
    async def test_create_slide_internal(self, slide_service, completed_deck):
        """Test internal slide creation (used by workers)."""
        await slide_service.deck_repo.create(completed_deck)
        original_version = completed_deck.version
        
        html_content = "<h1>New Slide</h1><p>Content with <script>alert('xss')</script></p>"
        presenter_notes = "Speaker notes"
        
        # Mock HTML sanitizer
        with patch('app.application.services.html_sanitizer') as mock_sanitizer:
            mock_sanitizer.sanitize.return_value = "<h1>New Slide</h1><p>Content with </p>"
            
            created_slide = await slide_service.create_slide(
                deck_id=completed_deck.id,
                slide_order=1,
                html_content=html_content,
                presenter_notes=presenter_notes
            )
        
        # Verify slide was created
        assert created_slide.deck_id == completed_deck.id
        assert created_slide.slide_order == 1
        assert created_slide.presenter_notes == presenter_notes
        
        # Verify HTML was sanitized
        mock_sanitizer.sanitize.assert_called_once_with(html_content)
        
        # Verify deck version was incremented and event was created
        updated_deck = await slide_service.deck_repo.get_by_id(completed_deck.id)
        assert updated_deck.version == original_version + 1
        
        events = slide_service.event_repo.events
        assert len(events) == 1
        assert events[0].event_type == "SlideAdded"

    @pytest.mark.asyncio
    async def test_update_slide_content_internal(self, slide_service, completed_deck, sample_slide):
        """Test internal slide content update (used by workers)."""
        await slide_service.deck_repo.create(completed_deck)
        original_version = completed_deck.version
        sample_slide.deck_id = completed_deck.id
        await slide_service.slide_repo.create(sample_slide)
        
        new_content = "<h1>Updated Slide</h1><p>New content</p>"
        new_notes = "Updated notes"
        
        # Mock HTML sanitizer
        with patch('app.application.services.html_sanitizer') as mock_sanitizer:
            mock_sanitizer.sanitize.return_value = new_content
            
            updated_slide = await slide_service.update_slide_content(
                slide_id=sample_slide.id,
                html_content=new_content,
                presenter_notes=new_notes
            )
        
        # Verify slide was updated
        assert updated_slide.html_content == new_content
        assert updated_slide.presenter_notes == new_notes
        
        # Verify deck version was incremented and event was created
        updated_deck = await slide_service.deck_repo.get_by_id(completed_deck.id)
        assert updated_deck.version == original_version + 1
        
        events = slide_service.event_repo.events
        assert len(events) == 1
        assert events[0].event_type == "SlideUpdated"

    @pytest.mark.asyncio
    async def test_update_slide_content_not_found(self, slide_service):
        """Test updating content of non-existent slide."""
        fake_slide_id = uuid4()
        
        with pytest.raises(DeckNotFoundException):
            await slide_service.update_slide_content(
                slide_id=fake_slide_id,
                html_content="<h1>Content</h1>",
                presenter_notes="Notes"
            )

    @pytest.mark.asyncio
    async def test_extract_title_from_html(self, slide_service):
        """Test HTML title extraction functionality."""
        # Test various HTML formats
        test_cases = [
            ("<h1>Main Title</h1><p>Content</p>", "Main Title"),
            ("<h2>Subtitle</h2><div>More content</div>", "Subtitle"),
            ("<div><h3>Nested Title</h3></div>", "Nested Title"),
            ("<p>No heading here</p>", "Untitled Slide"),
            ("<h1>  Whitespace Title  </h1>", "Whitespace Title"),
            ("", "Untitled Slide"),
        ]
        
        for html_content, expected_title in test_cases:
            actual_title = slide_service._extract_title_from_html(html_content)
            assert actual_title == expected_title

    @pytest.mark.asyncio
    async def test_service_error_handling(self, slide_service, sample_deck, test_user_id):
        """Test service error handling and logging."""
        # Mock stream publisher to raise exception
        slide_service.stream_publisher.publish_event.side_effect = Exception("Publishing failed")
        
        # Should log error but not raise exception
        await slide_service.deck_repo.create(sample_deck)
        
        with patch('app.application.services.html_sanitizer') as mock_sanitizer:
            mock_sanitizer.sanitize.return_value = "<h1>Test</h1>"
            
            slide = await slide_service.create_slide(
                deck_id=sample_deck.id,
                slide_order=1,
                html_content="<h1>Test</h1>"
            )
        
        # Slide should still be created despite publishing failure
        assert slide.deck_id == sample_deck.id


class TestServiceIntegration:
    """Test integration between services."""

    @pytest.mark.asyncio
    async def test_deck_and_slide_service_integration(self, test_user_id):
        """Test interaction between DeckService and SlideService."""
        # Create shared repositories
        deck_repo = FakeDeckRepository()
        slide_repo = FakeSlideRepository()
        event_repo = FakeEventRepository()
        
        # Create mock dependencies
        mock_stream_publisher = Mock()
        mock_stream_publisher.publish_event = AsyncMock()
        mock_cache_manager = Mock()
        mock_cache_manager.set_cancellation_flag = AsyncMock()
        mock_arq_redis = Mock()
        mock_arq_redis.enqueue_job = AsyncMock()
        
        # Create services with shared repositories
        deck_service = DeckService(
            deck_repo=deck_repo,
            slide_repo=slide_repo,
            event_repo=event_repo,
            stream_publisher=mock_stream_publisher,
            cache_manager=mock_cache_manager,
            arq_redis=mock_arq_redis,
        )
        
        slide_service = SlideService(
            slide_repo=slide_repo,
            deck_repo=deck_repo,
            event_repo=event_repo,
            stream_publisher=mock_stream_publisher,
            arq_redis=mock_arq_redis,
        )
        
        # Create deck using DeckService
        request = DeckCreationRequest(
            title="Integration Test Deck",
            topic="Testing service integration"
        )
        deck = await deck_service.create_deck(request, test_user_id)
        
        # Set deck to completed state
        deck.update_status(DeckStatus.COMPLETED)
        await deck_repo.update(deck)
        
        # Add slide using SlideService
        with patch('app.application.services.html_sanitizer') as mock_sanitizer:
            mock_sanitizer.sanitize.return_value = "<h1>Integration Test</h1>"
            
            slide = await slide_service.create_slide(
                deck_id=deck.id,
                slide_order=1,
                html_content="<h1>Integration Test</h1>"
            )
        
        # Retrieve deck with slides using DeckService
        retrieved_deck, slides = await deck_service.get_deck_with_slides(deck.id, test_user_id)
        
        # Verify integration
        assert retrieved_deck.id == deck.id
        assert len(slides) == 1
        assert slides[0].id == slide.id
        
        # Verify events from both services
        all_events = event_repo.events
        assert len(all_events) == 2  # DeckStarted + SlideAdded
        assert all_events[0].event_type == "DeckStarted"
        assert all_events[1].event_type == "SlideAdded"
