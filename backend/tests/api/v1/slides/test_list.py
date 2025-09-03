"""
Tests for slide listing endpoint.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock


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
            m.setattr(
                "app.api.v1.slides.list.DeckQueries", lambda session: mock_deck_query
            )

            mock_slide_repo = AsyncMock()
            mock_slide_repo.get_by_deck_id.return_value = [mock_slide]
            m.setattr(
                "app.api.v1.slides.list.SlideRepository",
                lambda session: mock_slide_repo,
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
            m.setattr(
                "app.api.v1.slides.list.DeckQueries", lambda session: mock_deck_query
            )

            mock_slide_repo = AsyncMock()
            mock_slide_repo.get_by_deck_id.return_value = mock_slides
            m.setattr(
                "app.api.v1.slides.list.SlideRepository",
                lambda session: mock_slide_repo,
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
            m.setattr(
                "app.api.v1.slides.list.DeckQueries", lambda session: mock_deck_query
            )

            response = client.get(
                f"/api/v1/decks/{deck_id}/slides", headers=auth_headers
            )

        assert response.status_code == 404

    def test_get_deck_slides_unauthorized(self, client, mock_dependencies):
        """Test slides retrieval without authentication."""
        deck_id = "12345678-1234-5678-9012-123456789012"

        response = client.get(f"/api/v1/decks/{deck_id}/slides")
        assert response.status_code == 401
