"""
Tests for Deck API endpoints.

Covers deck creation, status retrieval, slide listing, and deck-level operations.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID


class TestDeckCreation:
    """Test deck creation endpoint POST /api/v1/decks."""

    def test_create_deck_success(
        self, client, mock_dependencies, auth_headers, sample_deck_create_request
    ):
        """Test successful deck creation with all optional fields."""
        # Setup mocks
        mock_use_case_result = {
            "deck_id": "12345678-1234-5678-9012-123456789012",
            "status": "pending",
        }

        # Mock the use case execution
        with pytest.MonkeyPatch().context() as m:
            mock_use_case = AsyncMock()
            mock_use_case.execute.return_value = mock_use_case_result
            m.setattr(
                "app.api.v1.decks.CreateDeckPlanUseCase", lambda **kwargs: mock_use_case
            )

            # Make request
            response = client.post(
                "/api/v1/decks", json=sample_deck_create_request, headers=auth_headers
            )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "deck_id" in data
        assert data["status"] == "pending"
        assert "message" in data

        # Verify use case was called with correct parameters
        mock_use_case.execute.assert_called_once()
        call_args = mock_use_case.execute.call_args
        assert call_args.kwargs["prompt"] == sample_deck_create_request["prompt"]
        assert (
            call_args.kwargs["style_preferences"]
            == sample_deck_create_request["style_preferences"]
        )

    def test_create_deck_minimal_request(self, client, mock_dependencies, auth_headers):
        """Test deck creation with minimal required fields only."""
        minimal_request = {"prompt": "Create a simple presentation about Python basics"}

        mock_use_case_result = {
            "deck_id": "12345678-1234-5678-9012-123456789012",
            "status": "pending",
        }

        with pytest.MonkeyPatch().context() as m:
            mock_use_case = AsyncMock()
            mock_use_case.execute.return_value = mock_use_case_result
            m.setattr(
                "app.api.v1.decks.CreateDeckPlanUseCase", lambda **kwargs: mock_use_case
            )

            response = client.post(
                "/api/v1/decks", json=minimal_request, headers=auth_headers
            )

        assert response.status_code == 200
        data = response.json()
        assert UUID(data["deck_id"])  # Valid UUID
        assert data["status"] == "pending"

    def test_create_deck_validation_errors(
        self, client, mock_dependencies, auth_headers
    ):
        """Test validation errors for invalid deck creation requests."""

        # Test missing prompt
        response = client.post("/api/v1/decks", json={}, headers=auth_headers)
        assert response.status_code == 422

        # Test prompt too short
        response = client.post(
            "/api/v1/decks", json={"prompt": "short"}, headers=auth_headers
        )
        assert response.status_code == 422

        # Test invalid slide count
        response = client.post(
            "/api/v1/decks",
            json={
                "prompt": "Valid prompt for testing validation",
                "slide_count": 0,  # Invalid: must be >= 1
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_deck_unauthorized(self, client, mock_dependencies):
        """Test deck creation without authentication."""
        response = client.post(
            "/api/v1/decks", json={"prompt": "Test prompt without auth"}
        )
        assert response.status_code == 401

    def test_create_deck_use_case_error(
        self, client, mock_dependencies, auth_headers, sample_deck_create_request
    ):
        """Test handling of use case errors."""

        with pytest.MonkeyPatch().context() as m:
            mock_use_case = AsyncMock()
            mock_use_case.execute.side_effect = ValueError("Invalid prompt format")
            m.setattr(
                "app.api.v1.decks.CreateDeckPlanUseCase", lambda **kwargs: mock_use_case
            )

            response = client.post(
                "/api/v1/decks", json=sample_deck_create_request, headers=auth_headers
            )

        assert response.status_code == 400
        assert "Invalid prompt format" in response.json()["detail"]


class TestDeckStatus:
    """Test deck status endpoint GET /api/v1/decks/{deck_id}/status."""

    def test_get_deck_status_success(self, client, mock_dependencies, auth_headers):
        """Test successful deck status retrieval."""
        deck_id = "12345678-1234-5678-9012-123456789012"

        # Mock query response
        mock_deck_info = {
            "deck_id": deck_id,
            "status": "generating",
            "slide_count": 5,
            "created_at": "2023-12-01T10:00:00Z",
            "updated_at": "2023-12-01T10:30:00Z",
            "completed_at": None,
        }

        with pytest.MonkeyPatch().context() as m:
            mock_query = MagicMock()
            mock_query.get_deck_status.return_value = mock_deck_info
            m.setattr("app.api.v1.decks.DeckQueries", lambda session: mock_query)

            response = client.get(
                f"/api/v1/decks/{deck_id}/status", headers=auth_headers
            )

        assert response.status_code == 200
        data = response.json()
        assert data["deck_id"] == deck_id
        assert data["status"] == "generating"
        assert data["slide_count"] == 5
        assert "created_at" in data

    def test_get_deck_status_not_found(self, client, mock_dependencies, auth_headers):
        """Test deck status for non-existent deck."""
        deck_id = "00000000-0000-0000-0000-000000000000"

        with pytest.MonkeyPatch().context() as m:
            mock_query = MagicMock()
            mock_query.get_deck_status.return_value = None
            m.setattr("app.api.v1.decks.DeckQueries", lambda session: mock_query)

            response = client.get(
                f"/api/v1/decks/{deck_id}/status", headers=auth_headers
            )

        assert response.status_code == 404

    def test_get_deck_status_unauthorized(self, client, mock_dependencies):
        """Test deck status without authentication."""
        deck_id = "12345678-1234-5678-9012-123456789012"

        response = client.get(f"/api/v1/decks/{deck_id}/status")
        assert response.status_code == 401


class TestDeckSlides:
    """Test deck slides endpoint GET /api/v1/decks/{deck_id}/slides."""

    def test_get_deck_slides_success(
        self, client, mock_dependencies, auth_headers, sample_slide_data_api
    ):
        """Test successful deck slides retrieval."""
        deck_id = "12345678-1234-5678-9012-123456789012"

        # Mock deck verification
        mock_deck_info = {"deck_id": deck_id, "status": "completed"}

        # Mock slides
        mock_slide = MagicMock()
        mock_slide.id = "slide_123"
        mock_slide.deck_id = deck_id
        mock_slide.order = 1
        mock_slide.title = sample_slide_data_api["title"]
        mock_slide.content_outline = sample_slide_data_api["content_outline"]
        mock_slide.html_content = sample_slide_data_api["html_content"]
        mock_slide.presenter_notes = sample_slide_data_api["presenter_notes"]
        mock_slide.template_filename = sample_slide_data_api["template_type"]
        mock_slide.created_at = "2023-12-01T10:00:00Z"
        mock_slide.updated_at = "2023-12-01T10:30:00Z"

        with pytest.MonkeyPatch().context() as m:
            mock_deck_query = MagicMock()
            mock_deck_query.get_deck_status.return_value = mock_deck_info
            m.setattr("app.api.v1.decks.DeckQueries", lambda session: mock_deck_query)

            mock_slide_repo = AsyncMock()
            mock_slide_repo.get_by_deck_id.return_value = [mock_slide]
            m.setattr(
                "app.api.v1.decks.SlideRepository", lambda session: mock_slide_repo
            )

            response = client.get(
                f"/api/v1/decks/{deck_id}/slides", headers=auth_headers
            )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "pagination" in data
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == "slide_123"
        assert data["items"][0]["title"] == sample_slide_data_api["title"]

    def test_get_deck_slides_with_pagination(
        self, client, mock_dependencies, auth_headers
    ):
        """Test deck slides retrieval with pagination parameters."""
        deck_id = "12345678-1234-5678-9012-123456789012"

        # Mock deck verification
        mock_deck_info = {"deck_id": deck_id, "status": "completed"}

        # Mock multiple slides
        mock_slides = []
        for i in range(10):
            mock_slide = MagicMock()
            mock_slide.id = f"slide_{i}"
            mock_slide.deck_id = deck_id
            mock_slide.order = i + 1
            mock_slide.title = f"Slide {i + 1}"
            mock_slide.content_outline = f"Content for slide {i + 1}"
            mock_slide.html_content = f"<h1>Slide {i + 1}</h1>"
            mock_slide.presenter_notes = f"Notes for slide {i + 1}"
            mock_slide.template_filename = "professional"
            mock_slide.created_at = "2023-12-01T10:00:00Z"
            mock_slide.updated_at = "2023-12-01T10:30:00Z"
            mock_slides.append(mock_slide)

        with pytest.MonkeyPatch().context() as m:
            mock_deck_query = MagicMock()
            mock_deck_query.get_deck_status.return_value = mock_deck_info
            m.setattr("app.api.v1.decks.DeckQueries", lambda session: mock_deck_query)

            mock_slide_repo = AsyncMock()
            mock_slide_repo.get_by_deck_id.return_value = mock_slides
            m.setattr(
                "app.api.v1.decks.SlideRepository", lambda session: mock_slide_repo
            )

            response = client.get(
                f"/api/v1/decks/{deck_id}/slides?limit=5&offset=0", headers=auth_headers
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5  # Pagination applied
        assert data["pagination"]["total"] == 10
        assert data["pagination"]["limit"] == 5
        assert data["pagination"]["offset"] == 0

    def test_get_deck_slides_deck_not_found(
        self, client, mock_dependencies, auth_headers
    ):
        """Test slides retrieval for non-existent deck."""
        deck_id = "00000000-0000-0000-0000-000000000000"

        with pytest.MonkeyPatch().context() as m:
            mock_deck_query = MagicMock()
            mock_deck_query.get_deck_status.return_value = None
            m.setattr("app.api.v1.decks.DeckQueries", lambda session: mock_deck_query)

            response = client.get(
                f"/api/v1/decks/{deck_id}/slides", headers=auth_headers
            )

        assert response.status_code == 404


class TestSlideInsertion:
    """Test slide insertion endpoint POST /api/v1/decks/{deck_id}/slides."""

    def test_insert_slide_success(self, client, mock_dependencies, auth_headers):
        """Test successful slide insertion."""
        deck_id = "12345678-1234-5678-9012-123456789012"

        request_data = {
            "position": 2,
            "seed_outline": "Introduction to advanced concepts",
            "template_type": "professional",
        }

        # Mock deck verification
        mock_deck_info = {"deck_id": deck_id, "status": "editing"}

        # Mock existing slides
        mock_existing_slides = [
            MagicMock(id="slide_1", order=1),
            MagicMock(id="slide_2", order=2),
            MagicMock(id="slide_3", order=3),
        ]

        # Mock created slide
        mock_created_slide = MagicMock()
        mock_created_slide.id = "new_slide_123"
        mock_created_slide.deck_id = deck_id
        mock_created_slide.order = 2
        mock_created_slide.title = "New Slide"
        mock_created_slide.content_outline = request_data["seed_outline"]
        mock_created_slide.html_content = None
        mock_created_slide.presenter_notes = None
        mock_created_slide.template_filename = request_data["template_type"]
        mock_created_slide.created_at = "2023-12-01T10:00:00Z"
        mock_created_slide.updated_at = None

        with pytest.MonkeyPatch().context() as m:
            mock_deck_query = MagicMock()
            mock_deck_query.get_deck_status.return_value = mock_deck_info
            m.setattr("app.api.v1.decks.DeckQueries", lambda session: mock_deck_query)

            mock_slide_repo = AsyncMock()
            mock_slide_repo.get_by_deck_id.return_value = mock_existing_slides
            mock_slide_repo.create.return_value = mock_created_slide
            mock_slide_repo.update = AsyncMock()  # For reordering existing slides
            m.setattr(
                "app.api.v1.decks.SlideRepository", lambda session: mock_slide_repo
            )

            response = client.post(
                f"/api/v1/decks/{deck_id}/slides",
                json=request_data,
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "new_slide_123"
        assert data["order"] == 2
        assert data["content_outline"] == request_data["seed_outline"]

    def test_insert_slide_after_existing(self, client, mock_dependencies, auth_headers):
        """Test inserting slide after a specific existing slide."""
        deck_id = "12345678-1234-5678-9012-123456789012"

        request_data = {
            "after_slide_id": "slide_1",
            "seed_outline": "Follow-up content",
            "template_type": "professional",
        }

        # Mock existing slides
        mock_existing_slides = [
            MagicMock(id="slide_1", order=1),
            MagicMock(id="slide_2", order=2),
            MagicMock(id="slide_3", order=3),
        ]

        # Mock created slide
        mock_created_slide = MagicMock()
        mock_created_slide.id = "new_slide_after"
        mock_created_slide.deck_id = deck_id
        mock_created_slide.order = 2
        mock_created_slide.title = "New Slide"
        mock_created_slide.content_outline = request_data["seed_outline"]
        mock_created_slide.html_content = None
        mock_created_slide.presenter_notes = None
        mock_created_slide.template_filename = request_data["template_type"]
        mock_created_slide.created_at = "2023-12-01T10:05:00Z"
        mock_created_slide.updated_at = None

        with pytest.MonkeyPatch().context() as m:
            mock_deck_query = MagicMock()
            mock_deck_query.get_deck_status.return_value = {
                "deck_id": deck_id,
                "status": "editing",
            }
            m.setattr("app.api.v1.decks.DeckQueries", lambda session: mock_deck_query)

            mock_slide_repo = AsyncMock()
            mock_slide_repo.get_by_deck_id.return_value = mock_existing_slides
            mock_slide_repo.create.return_value = mock_created_slide
            mock_slide_repo.update = AsyncMock()
            m.setattr(
                "app.api.v1.decks.SlideRepository", lambda session: mock_slide_repo
            )

            response = client.post(
                f"/api/v1/decks/{deck_id}/slides",
                json=request_data,
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "new_slide_after"
        assert data["order"] == 2
        assert data["content_outline"] == request_data["seed_outline"]


class TestDeckEvents:
    """Test deck events endpoint GET /api/v1/decks/{deck_id}/events."""

    def test_get_deck_events_success(self, client, mock_dependencies, auth_headers):
        """Test successful deck events retrieval."""
        deck_id = "12345678-1234-5678-9012-123456789012"

        # Mock deck verification
        mock_deck_info = {"deck_id": deck_id, "status": "completed"}

        with pytest.MonkeyPatch().context() as m:
            mock_deck_query = MagicMock()
            mock_deck_query.get_deck_status.return_value = mock_deck_info
            m.setattr("app.api.v1.decks.DeckQueries", lambda session: mock_deck_query)

            response = client.get(
                f"/api/v1/decks/{deck_id}/events", headers=auth_headers
            )

        assert response.status_code == 200
        # Currently returns empty list as per implementation
        data = response.json()
        assert isinstance(data, list)


class TestDeckCancel:
    """Tests for deck cancellation endpoint POST /api/v1/decks/{deck_id}/cancel."""

    def test_cancel_deck_success(self, client, mock_dependencies, auth_headers):
        deck_id = "12345678-1234-5678-9012-123456789012"

        with pytest.MonkeyPatch().context() as m:
            # Deck exists and is cancellable (generating)
            mock_deck_query = MagicMock()
            mock_deck_query.get_deck_status.return_value = {
                "deck_id": deck_id,
                "status": "generating",
            }
            m.setattr("app.api.v1.decks.DeckQueries", lambda session: mock_deck_query)

            # Redis client mock with setex
            class _FakeRedis:
                async def setex(self, *args, **kwargs):
                    return True

            async def _fake_get_redis_client():
                return _FakeRedis()

            m.setattr("app.api.v1.decks.get_redis_client", _fake_get_redis_client)

            res = client.post(f"/api/v1/decks/{deck_id}/cancel", headers=auth_headers)

        assert res.status_code == 200
        data = res.json()
        assert data["deck_id"] == deck_id
        assert "Cancellation request received" in data["message"]

    def test_cancel_deck_not_found(self, client, mock_dependencies, auth_headers):
        deck_id = "00000000-0000-0000-0000-000000000000"

        with pytest.MonkeyPatch().context() as m:
            mock_deck_query = MagicMock()
            mock_deck_query.get_deck_status.return_value = None
            m.setattr("app.api.v1.decks.DeckQueries", lambda session: mock_deck_query)

            res = client.post(f"/api/v1/decks/{deck_id}/cancel", headers=auth_headers)

        assert res.status_code == 404

    def test_cancel_deck_invalid_status(self, client, mock_dependencies, auth_headers):
        deck_id = "12345678-1234-5678-9012-123456789012"

        with pytest.MonkeyPatch().context() as m:
            mock_deck_query = MagicMock()
            mock_deck_query.get_deck_status.return_value = {
                "deck_id": deck_id,
                "status": "completed",
            }
            m.setattr("app.api.v1.decks.DeckQueries", lambda session: mock_deck_query)

            res = client.post(f"/api/v1/decks/{deck_id}/cancel", headers=auth_headers)

        assert res.status_code == 400
