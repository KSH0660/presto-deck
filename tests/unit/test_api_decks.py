"""Unit tests for deck API endpoints."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.schemas import (
    DeckCreationRequest,
    DeckCreationResponse,
    DeckResponse,
    DeckListResponse,
    CancellationResponse,
    SlideResponse,
)
from app.api.v1.decks import router
from app.domain.entities import Deck, DeckStatus, Slide
from app.domain.exceptions import (
    DeckNotFoundException,
    UnauthorizedAccessException,
    InvalidDeckStatusException,
)


class TestCreateDeckEndpoint:
    """Test cases for POST /decks endpoint."""

    @pytest.fixture
    def mock_deck_service(self):
        """Create mock deck service."""
        return AsyncMock()

    @pytest.fixture
    def mock_get_current_user_id(self):
        """Create mock dependency for current user ID."""
        return AsyncMock(return_value="test-user-123")

    @pytest.fixture
    def mock_get_deck_service(self, mock_deck_service):
        """Create mock dependency for deck service."""
        return AsyncMock(return_value=mock_deck_service)

    @pytest.fixture
    def sample_deck_request(self):
        """Create sample deck creation request."""
        return DeckCreationRequest(
            title="AI Strategy 2024",
            topic="How to leverage AI in business operations for competitive advantage",
            audience="C-level executives and decision makers",
            style="professional",
            slide_count=8,
            language="en",
            include_speaker_notes=True,
        )

    @pytest.fixture
    def sample_deck(self):
        """Create sample deck entity."""
        return Deck(
            id=uuid4(),
            user_id="test-user-123",
            title="AI Strategy 2024",
            status=DeckStatus.PENDING,
            version=1,
        )

    @pytest.mark.asyncio
    async def test_create_deck_success(self, sample_deck_request, sample_deck, mock_deck_service):
        """Test successful deck creation."""
        # Setup
        mock_deck_service.create_deck.return_value = sample_deck
        
        with patch('app.api.v1.decks.get_current_user_id', return_value="test-user-123"), \
             patch('app.api.v1.decks.get_deck_service', return_value=mock_deck_service), \
             patch('app.core.observability.metrics.record_http_request') as mock_metrics, \
             patch('app.core.observability.trace_async_operation'):

            from app.api.v1.decks import create_deck
            
            response = await create_deck(
                request=sample_deck_request,
                user_id="test-user-123",
                deck_service=mock_deck_service,
            )

        # Assertions
        assert isinstance(response, DeckCreationResponse)
        assert response.deck_id == sample_deck.id
        assert response.status == DeckStatus.PENDING
        assert response.message == "Deck creation started successfully"
        
        mock_deck_service.create_deck.assert_called_once_with(sample_deck_request, "test-user-123")
        mock_metrics.assert_called_with("POST", "/api/v1/decks", 202, 0.0)

    @pytest.mark.asyncio
    async def test_create_deck_service_error(self, sample_deck_request, mock_deck_service):
        """Test deck creation with service error."""
        # Setup
        mock_deck_service.create_deck.side_effect = Exception("Service error")
        
        with patch('app.api.v1.decks.get_current_user_id', return_value="test-user-123"), \
             patch('app.api.v1.decks.get_deck_service', return_value=mock_deck_service), \
             patch('app.core.observability.metrics.record_http_request') as mock_metrics, \
             patch('app.core.observability.trace_async_operation'):

            from app.api.v1.decks import create_deck
            
            with pytest.raises(HTTPException) as exc:
                await create_deck(
                    request=sample_deck_request,
                    user_id="test-user-123",
                    deck_service=mock_deck_service,
                )

        # Assertions
        assert exc.value.status_code == 500
        assert "Service error" in str(exc.value.detail)
        mock_metrics.assert_called_with("POST", "/api/v1/decks", 500, 0.0)

    def test_deck_creation_request_validation(self):
        """Test deck creation request validation."""
        # Valid request
        valid_request = DeckCreationRequest(
            title="Valid Title",
            topic="This is a valid topic with enough characters",
            slide_count=5,
        )
        assert valid_request.title == "Valid Title"
        assert valid_request.slide_count == 5

        # Invalid title - empty
        with pytest.raises(ValueError):
            DeckCreationRequest(
                title="",
                topic="Valid topic",
            )

        # Invalid topic - too short
        with pytest.raises(ValueError):
            DeckCreationRequest(
                title="Valid Title",
                topic="Short",
            )

        # Invalid slide count - too few
        with pytest.raises(ValueError):
            DeckCreationRequest(
                title="Valid Title",
                topic="Valid topic with enough characters",
                slide_count=1,
            )

        # Invalid slide count - too many
        with pytest.raises(ValueError):
            DeckCreationRequest(
                title="Valid Title",
                topic="Valid topic with enough characters",
                slide_count=25,
            )


class TestGetDeckEndpoint:
    """Test cases for GET /decks/{deck_id} endpoint."""

    @pytest.fixture
    def sample_deck(self):
        """Create sample deck entity."""
        return Deck(
            id=uuid4(),
            user_id="test-user-123",
            title="Test Deck",
            status=DeckStatus.COMPLETED,
            version=3,
            deck_plan={"title": "Test Deck", "slides": []},
        )

    @pytest.fixture
    def sample_slides(self, sample_deck):
        """Create sample slide entities."""
        return [
            Slide(
                id=uuid4(),
                deck_id=sample_deck.id,
                slide_order=1,
                html_content="<h1>Slide 1</h1>",
                presenter_notes="Notes for slide 1",
            ),
            Slide(
                id=uuid4(),
                deck_id=sample_deck.id,
                slide_order=2,
                html_content="<h1>Slide 2</h1>",
                presenter_notes="Notes for slide 2",
            ),
        ]

    @pytest.mark.asyncio
    async def test_get_deck_success(self, sample_deck, sample_slides):
        """Test successful deck retrieval."""
        mock_deck_service = AsyncMock()
        mock_deck_service.get_deck_with_slides.return_value = (sample_deck, sample_slides)
        
        with patch('app.api.v1.decks.get_current_user_id', return_value="test-user-123"), \
             patch('app.api.v1.decks.get_deck_service', return_value=mock_deck_service), \
             patch('app.core.observability.metrics.record_http_request') as mock_metrics, \
             patch('app.core.observability.trace_async_operation'):

            from app.api.v1.decks import get_deck
            
            response = await get_deck(
                deck_id=sample_deck.id,
                user_id="test-user-123",
                deck_service=mock_deck_service,
            )

        # Assertions
        assert isinstance(response, DeckResponse)
        assert response.id == sample_deck.id
        assert response.user_id == sample_deck.user_id
        assert response.title == sample_deck.title
        assert response.status == DeckStatus.COMPLETED
        assert response.version == 3
        assert len(response.slides) == 2
        
        # Check slide data
        for i, slide_response in enumerate(response.slides):
            assert isinstance(slide_response, SlideResponse)
            assert slide_response.id == sample_slides[i].id
            assert slide_response.slide_order == i + 1
            assert slide_response.html_content == f"<h1>Slide {i + 1}</h1>"
        
        mock_deck_service.get_deck_with_slides.assert_called_once_with(sample_deck.id, "test-user-123")
        mock_metrics.assert_called_with("GET", f"/api/v1/decks/{sample_deck.id}", 200, 0.0)

    @pytest.mark.asyncio
    async def test_get_deck_not_found(self):
        """Test deck retrieval when deck not found."""
        deck_id = uuid4()
        mock_deck_service = AsyncMock()
        mock_deck_service.get_deck_with_slides.side_effect = DeckNotFoundException(f"Deck {deck_id} not found")
        
        with patch('app.api.v1.decks.get_current_user_id', return_value="test-user-123"), \
             patch('app.api.v1.decks.get_deck_service', return_value=mock_deck_service), \
             patch('app.core.observability.metrics.record_http_request') as mock_metrics, \
             patch('app.core.observability.trace_async_operation'):

            from app.api.v1.decks import get_deck
            
            with pytest.raises(HTTPException) as exc:
                await get_deck(
                    deck_id=deck_id,
                    user_id="test-user-123",
                    deck_service=mock_deck_service,
                )

        # Assertions
        assert exc.value.status_code == 404
        assert f"Deck {deck_id} not found" in str(exc.value.detail)
        mock_metrics.assert_called_with("GET", f"/api/v1/decks/{deck_id}", 404, 0.0)

    @pytest.mark.asyncio
    async def test_get_deck_unauthorized(self):
        """Test deck retrieval when user unauthorized."""
        deck_id = uuid4()
        mock_deck_service = AsyncMock()
        mock_deck_service.get_deck_with_slides.side_effect = UnauthorizedAccessException("Access denied")
        
        with patch('app.api.v1.decks.get_current_user_id', return_value="test-user-123"), \
             patch('app.api.v1.decks.get_deck_service', return_value=mock_deck_service), \
             patch('app.core.observability.metrics.record_http_request') as mock_metrics, \
             patch('app.core.observability.trace_async_operation'):

            from app.api.v1.decks import get_deck
            
            with pytest.raises(HTTPException) as exc:
                await get_deck(
                    deck_id=deck_id,
                    user_id="test-user-123",
                    deck_service=mock_deck_service,
                )

        # Assertions
        assert exc.value.status_code == 403
        assert "Access denied" in str(exc.value.detail)
        mock_metrics.assert_called_with("GET", f"/api/v1/decks/{deck_id}", 403, 0.0)

    @pytest.mark.asyncio
    async def test_get_deck_service_error(self):
        """Test deck retrieval with service error."""
        deck_id = uuid4()
        mock_deck_service = AsyncMock()
        mock_deck_service.get_deck_with_slides.side_effect = Exception("Service error")
        
        with patch('app.api.v1.decks.get_current_user_id', return_value="test-user-123"), \
             patch('app.api.v1.decks.get_deck_service', return_value=mock_deck_service), \
             patch('app.core.observability.metrics.record_http_request') as mock_metrics, \
             patch('app.core.observability.trace_async_operation'):

            from app.api.v1.decks import get_deck
            
            with pytest.raises(HTTPException) as exc:
                await get_deck(
                    deck_id=deck_id,
                    user_id="test-user-123",
                    deck_service=mock_deck_service,
                )

        # Assertions
        assert exc.value.status_code == 500
        assert "Service error" in str(exc.value.detail)
        mock_metrics.assert_called_with("GET", f"/api/v1/decks/{deck_id}", 500, 0.0)


class TestListDecksEndpoint:
    """Test cases for GET /decks endpoint."""

    @pytest.fixture
    def sample_decks(self):
        """Create sample deck entities."""
        return [
            Deck(
                id=uuid4(),
                user_id="test-user-123",
                title="Deck 1",
                status=DeckStatus.COMPLETED,
                version=1,
            ),
            Deck(
                id=uuid4(),
                user_id="test-user-123",
                title="Deck 2",
                status=DeckStatus.PENDING,
                version=1,
            ),
            Deck(
                id=uuid4(),
                user_id="test-user-123",
                title="Deck 3",
                status=DeckStatus.GENERATING,
                version=2,
            ),
        ]

    @pytest.mark.asyncio
    async def test_list_decks_success(self, sample_decks):
        """Test successful deck listing."""
        mock_deck_service = AsyncMock()
        mock_deck_service.list_decks.return_value = sample_decks
        
        # Mock get_deck_with_slides to return slides for slide count
        slides_by_deck = {
            sample_decks[0].id: [Mock(), Mock()],  # 2 slides
            sample_decks[1].id: [Mock()],  # 1 slide
            sample_decks[2].id: [Mock(), Mock(), Mock()],  # 3 slides
        }
        
        async def mock_get_deck_with_slides(deck_id, user_id):
            deck = next(d for d in sample_decks if d.id == deck_id)
            return deck, slides_by_deck[deck_id]
        
        mock_deck_service.get_deck_with_slides.side_effect = mock_get_deck_with_slides
        
        with patch('app.api.v1.decks.get_current_user_id', return_value="test-user-123"), \
             patch('app.api.v1.decks.get_deck_service', return_value=mock_deck_service), \
             patch('app.core.observability.metrics.record_http_request') as mock_metrics, \
             patch('app.core.observability.trace_async_operation'):

            from app.api.v1.decks import list_decks
            
            response = await list_decks(
                limit=10,
                offset=0,
                user_id="test-user-123",
                deck_service=mock_deck_service,
            )

        # Assertions
        assert isinstance(response, list)
        assert len(response) == 3
        
        for i, deck_response in enumerate(response):
            assert isinstance(deck_response, DeckListResponse)
            assert deck_response.id == sample_decks[i].id
            assert deck_response.title == sample_decks[i].title
            assert deck_response.status == sample_decks[i].status
        
        # Check slide counts
        assert response[0].slide_count == 2
        assert response[1].slide_count == 1
        assert response[2].slide_count == 3
        
        mock_deck_service.list_decks.assert_called_once_with("test-user-123", 10, 0)
        mock_metrics.assert_called_with("GET", "/api/v1/decks", 200, 0.0)

    @pytest.mark.asyncio
    async def test_list_decks_empty_result(self):
        """Test deck listing with no decks."""
        mock_deck_service = AsyncMock()
        mock_deck_service.list_decks.return_value = []
        
        with patch('app.api.v1.decks.get_current_user_id', return_value="test-user-123"), \
             patch('app.api.v1.decks.get_deck_service', return_value=mock_deck_service), \
             patch('app.core.observability.metrics.record_http_request') as mock_metrics, \
             patch('app.core.observability.trace_async_operation'):

            from app.api.v1.decks import list_decks
            
            response = await list_decks(
                limit=10,
                offset=0,
                user_id="test-user-123",
                deck_service=mock_deck_service,
            )

        # Assertions
        assert isinstance(response, list)
        assert len(response) == 0
        mock_metrics.assert_called_with("GET", "/api/v1/decks", 200, 0.0)

    @pytest.mark.asyncio
    async def test_list_decks_with_pagination(self, sample_decks):
        """Test deck listing with pagination parameters."""
        mock_deck_service = AsyncMock()
        mock_deck_service.list_decks.return_value = sample_decks[:2]  # Return first 2 decks
        
        # Mock get_deck_with_slides
        async def mock_get_deck_with_slides(deck_id, user_id):
            deck = next(d for d in sample_decks[:2] if d.id == deck_id)
            return deck, [Mock()]  # 1 slide each
        
        mock_deck_service.get_deck_with_slides.side_effect = mock_get_deck_with_slides
        
        with patch('app.api.v1.decks.get_current_user_id', return_value="test-user-123"), \
             patch('app.api.v1.decks.get_deck_service', return_value=mock_deck_service), \
             patch('app.core.observability.trace_async_operation'):

            from app.api.v1.decks import list_decks
            
            response = await list_decks(
                limit=2,
                offset=10,
                user_id="test-user-123",
                deck_service=mock_deck_service,
            )

        # Assertions
        assert len(response) == 2
        mock_deck_service.list_decks.assert_called_once_with("test-user-123", 2, 10)

    @pytest.mark.asyncio
    async def test_list_decks_service_error(self):
        """Test deck listing with service error."""
        mock_deck_service = AsyncMock()
        mock_deck_service.list_decks.side_effect = Exception("Service error")
        
        with patch('app.api.v1.decks.get_current_user_id', return_value="test-user-123"), \
             patch('app.api.v1.decks.get_deck_service', return_value=mock_deck_service), \
             patch('app.core.observability.metrics.record_http_request') as mock_metrics, \
             patch('app.core.observability.trace_async_operation'):

            from app.api.v1.decks import list_decks
            
            with pytest.raises(HTTPException) as exc:
                await list_decks(
                    limit=10,
                    offset=0,
                    user_id="test-user-123",
                    deck_service=mock_deck_service,
                )

        # Assertions
        assert exc.value.status_code == 500
        assert "Service error" in str(exc.value.detail)
        mock_metrics.assert_called_with("GET", "/api/v1/decks", 500, 0.0)


class TestCancelDeckEndpoint:
    """Test cases for POST /decks/{deck_id}/cancel endpoint."""

    @pytest.fixture
    def sample_deck(self):
        """Create sample deck entity."""
        return Deck(
            id=uuid4(),
            user_id="test-user-123",
            title="Test Deck",
            status=DeckStatus.CANCELLED,
            version=1,
        )

    @pytest.mark.asyncio
    async def test_cancel_deck_success(self, sample_deck):
        """Test successful deck cancellation."""
        mock_deck_service = AsyncMock()
        mock_deck_service.cancel_deck_generation.return_value = sample_deck
        
        with patch('app.api.v1.decks.get_current_user_id', return_value="test-user-123"), \
             patch('app.api.v1.decks.get_deck_service', return_value=mock_deck_service), \
             patch('app.core.observability.metrics.record_http_request') as mock_metrics, \
             patch('app.core.observability.trace_async_operation'):

            from app.api.v1.decks import cancel_deck_generation
            
            response = await cancel_deck_generation(
                deck_id=sample_deck.id,
                user_id="test-user-123",
                deck_service=mock_deck_service,
            )

        # Assertions
        assert isinstance(response, CancellationResponse)
        assert response.deck_id == sample_deck.id
        assert response.status == DeckStatus.CANCELLED
        assert response.message == "Deck generation cancellation requested"
        
        mock_deck_service.cancel_deck_generation.assert_called_once_with(sample_deck.id, "test-user-123")
        mock_metrics.assert_called_with("POST", f"/api/v1/decks/{sample_deck.id}/cancel", 202, 0.0)

    @pytest.mark.asyncio
    async def test_cancel_deck_not_found(self):
        """Test deck cancellation when deck not found."""
        deck_id = uuid4()
        mock_deck_service = AsyncMock()
        mock_deck_service.cancel_deck_generation.side_effect = DeckNotFoundException(f"Deck {deck_id} not found")
        
        with patch('app.api.v1.decks.get_current_user_id', return_value="test-user-123"), \
             patch('app.api.v1.decks.get_deck_service', return_value=mock_deck_service), \
             patch('app.core.observability.metrics.record_http_request') as mock_metrics, \
             patch('app.core.observability.trace_async_operation'):

            from app.api.v1.decks import cancel_deck_generation
            
            with pytest.raises(HTTPException) as exc:
                await cancel_deck_generation(
                    deck_id=deck_id,
                    user_id="test-user-123",
                    deck_service=mock_deck_service,
                )

        # Assertions
        assert exc.value.status_code == 404
        assert f"Deck {deck_id} not found" in str(exc.value.detail)
        mock_metrics.assert_called_with("POST", f"/api/v1/decks/{deck_id}/cancel", 404, 0.0)

    @pytest.mark.asyncio
    async def test_cancel_deck_unauthorized(self):
        """Test deck cancellation when user unauthorized."""
        deck_id = uuid4()
        mock_deck_service = AsyncMock()
        mock_deck_service.cancel_deck_generation.side_effect = UnauthorizedAccessException("Access denied")
        
        with patch('app.api.v1.decks.get_current_user_id', return_value="test-user-123"), \
             patch('app.api.v1.decks.get_deck_service', return_value=mock_deck_service), \
             patch('app.core.observability.metrics.record_http_request') as mock_metrics, \
             patch('app.core.observability.trace_async_operation'):

            from app.api.v1.decks import cancel_deck_generation
            
            with pytest.raises(HTTPException) as exc:
                await cancel_deck_generation(
                    deck_id=deck_id,
                    user_id="test-user-123",
                    deck_service=mock_deck_service,
                )

        # Assertions
        assert exc.value.status_code == 403
        assert "Access denied" in str(exc.value.detail)
        mock_metrics.assert_called_with("POST", f"/api/v1/decks/{deck_id}/cancel", 403, 0.0)

    @pytest.mark.asyncio
    async def test_cancel_deck_invalid_status(self):
        """Test deck cancellation with invalid status."""
        deck_id = uuid4()
        mock_deck_service = AsyncMock()
        mock_deck_service.cancel_deck_generation.side_effect = InvalidDeckStatusException(
            str(deck_id), "COMPLETED", "PENDING, PLANNING, or GENERATING"
        )
        
        with patch('app.api.v1.decks.get_current_user_id', return_value="test-user-123"), \
             patch('app.api.v1.decks.get_deck_service', return_value=mock_deck_service), \
             patch('app.core.observability.metrics.record_http_request') as mock_metrics, \
             patch('app.core.observability.trace_async_operation'):

            from app.api.v1.decks import cancel_deck_generation
            
            with pytest.raises(HTTPException) as exc:
                await cancel_deck_generation(
                    deck_id=deck_id,
                    user_id="test-user-123",
                    deck_service=mock_deck_service,
                )

        # Assertions
        assert exc.value.status_code == 400
        assert "status COMPLETED" in str(exc.value.detail)
        mock_metrics.assert_called_with("POST", f"/api/v1/decks/{deck_id}/cancel", 400, 0.0)


class TestGetDeckEventsEndpoint:
    """Test cases for GET /decks/{deck_id}/events endpoint."""

    @pytest.fixture
    def sample_events(self):
        """Create sample deck events."""
        from app.domain.entities import DeckEvent
        return [
            DeckEvent(
                id=1,
                deck_id=uuid4(),
                version=1,
                event_type="DeckStarted",
                payload={"title": "Test Deck"},
                created_at=datetime(2024, 1, 1, 10, 0, 0),
            ),
            DeckEvent(
                id=2,
                deck_id=uuid4(),
                version=2,
                event_type="SlideAdded",
                payload={"slide_id": "123", "order": 1},
                created_at=datetime(2024, 1, 1, 10, 1, 0),
            ),
        ]

    @pytest.mark.asyncio
    async def test_get_deck_events_success(self, sample_events):
        """Test successful deck events retrieval."""
        deck_id = uuid4()
        mock_deck_service = AsyncMock()
        mock_deck_service.get_deck_events.return_value = sample_events
        
        with patch('app.api.v1.decks.get_current_user_id', return_value="test-user-123"), \
             patch('app.api.v1.decks.get_deck_service', return_value=mock_deck_service), \
             patch('app.core.observability.metrics.record_http_request') as mock_metrics, \
             patch('app.core.observability.trace_async_operation'):

            from app.api.v1.decks import get_deck_events
            
            response = await get_deck_events(
                deck_id=deck_id,
                from_version=0,
                user_id="test-user-123",
                deck_service=mock_deck_service,
            )

        # Assertions
        assert "events" in response
        events = response["events"]
        assert len(events) == 2
        
        # Check first event
        assert events[0]["event_type"] == "DeckStarted"
        assert events[0]["version"] == 1
        assert events[0]["payload"] == {"title": "Test Deck"}
        assert events[0]["timestamp"] == "2024-01-01T10:00:00"
        
        # Check second event
        assert events[1]["event_type"] == "SlideAdded"
        assert events[1]["version"] == 2
        assert events[1]["payload"] == {"slide_id": "123", "order": 1}
        
        mock_deck_service.get_deck_events.assert_called_once_with(deck_id, "test-user-123", 0)
        mock_metrics.assert_called_with("GET", f"/api/v1/decks/{deck_id}/events", 200, 0.0)

    @pytest.mark.asyncio
    async def test_get_deck_events_with_from_version(self, sample_events):
        """Test deck events retrieval with from_version parameter."""
        deck_id = uuid4()
        mock_deck_service = AsyncMock()
        mock_deck_service.get_deck_events.return_value = sample_events[1:]  # Skip first event
        
        with patch('app.api.v1.decks.get_current_user_id', return_value="test-user-123"), \
             patch('app.api.v1.decks.get_deck_service', return_value=mock_deck_service), \
             patch('app.core.observability.trace_async_operation'):

            from app.api.v1.decks import get_deck_events
            
            response = await get_deck_events(
                deck_id=deck_id,
                from_version=1,
                user_id="test-user-123",
                deck_service=mock_deck_service,
            )

        # Assertions
        assert len(response["events"]) == 1
        assert response["events"][0]["version"] == 2
        mock_deck_service.get_deck_events.assert_called_once_with(deck_id, "test-user-123", 1)

    @pytest.mark.asyncio
    async def test_get_deck_events_not_found(self):
        """Test deck events retrieval when deck not found."""
        deck_id = uuid4()
        mock_deck_service = AsyncMock()
        mock_deck_service.get_deck_events.side_effect = DeckNotFoundException(f"Deck {deck_id} not found")
        
        with patch('app.api.v1.decks.get_current_user_id', return_value="test-user-123"), \
             patch('app.api.v1.decks.get_deck_service', return_value=mock_deck_service), \
             patch('app.core.observability.metrics.record_http_request') as mock_metrics, \
             patch('app.core.observability.trace_async_operation'):

            from app.api.v1.decks import get_deck_events
            
            with pytest.raises(HTTPException) as exc:
                await get_deck_events(
                    deck_id=deck_id,
                    from_version=0,
                    user_id="test-user-123",
                    deck_service=mock_deck_service,
                )

        # Assertions
        assert exc.value.status_code == 404
        assert f"Deck {deck_id} not found" in str(exc.value.detail)
        mock_metrics.assert_called_with("GET", f"/api/v1/decks/{deck_id}/events", 404, 0.0)

    @pytest.mark.asyncio
    async def test_get_deck_events_unauthorized(self):
        """Test deck events retrieval when user unauthorized."""
        deck_id = uuid4()
        mock_deck_service = AsyncMock()
        mock_deck_service.get_deck_events.side_effect = UnauthorizedAccessException("Access denied")
        
        with patch('app.api.v1.decks.get_current_user_id', return_value="test-user-123"), \
             patch('app.api.v1.decks.get_deck_service', return_value=mock_deck_service), \
             patch('app.core.observability.metrics.record_http_request') as mock_metrics, \
             patch('app.core.observability.trace_async_operation'):

            from app.api.v1.decks import get_deck_events
            
            with pytest.raises(HTTPException) as exc:
                await get_deck_events(
                    deck_id=deck_id,
                    from_version=0,
                    user_id="test-user-123",
                    deck_service=mock_deck_service,
                )

        # Assertions
        assert exc.value.status_code == 403
        assert "Access denied" in str(exc.value.detail)
        mock_metrics.assert_called_with("GET", f"/api/v1/decks/{deck_id}/events", 403, 0.0)
