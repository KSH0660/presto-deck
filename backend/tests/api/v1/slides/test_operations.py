"""
Tests for slide operations endpoint.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock


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
        mock_created_slide.presenter_notes = ""
        mock_created_slide.template_filename = request_data["template_type"]
        mock_created_slide.created_at = "2023-12-01T10:00:00Z"
        mock_created_slide.updated_at = None

        with pytest.MonkeyPatch().context() as m:
            mock_deck_query = MagicMock()
            mock_deck_query.get_deck_status.return_value = mock_deck_info
            m.setattr(
                "app.api.v1.slides.operations.DeckQueries",
                lambda session: mock_deck_query,
            )

            mock_slide_repo = AsyncMock()
            mock_slide_repo.get_by_deck_id.return_value = mock_existing_slides
            mock_slide_repo.create.return_value = mock_created_slide
            mock_slide_repo.update = AsyncMock()  # For reordering existing slides
            m.setattr(
                "app.api.v1.slides.operations.SlideRepository",
                lambda session: mock_slide_repo,
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
        mock_created_slide.presenter_notes = ""
        mock_created_slide.template_filename = request_data["template_type"]
        mock_created_slide.created_at = "2023-12-01T10:05:00Z"
        mock_created_slide.updated_at = None

        with pytest.MonkeyPatch().context() as m:
            mock_deck_query = MagicMock()
            mock_deck_query.get_deck_status.return_value = {
                "deck_id": deck_id,
                "status": "editing",
            }
            m.setattr(
                "app.api.v1.slides.operations.DeckQueries",
                lambda session: mock_deck_query,
            )

            mock_slide_repo = AsyncMock()
            mock_slide_repo.get_by_deck_id.return_value = mock_existing_slides
            mock_slide_repo.create.return_value = mock_created_slide
            mock_slide_repo.update = AsyncMock()
            m.setattr(
                "app.api.v1.slides.operations.SlideRepository",
                lambda session: mock_slide_repo,
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

    def test_insert_slide_deck_not_found(self, client, mock_dependencies, auth_headers):
        """Test slide insertion for non-existent deck."""
        deck_id = "00000000-0000-0000-0000-000000000000"

        request_data = {
            "position": 1,
            "seed_outline": "Test content",
            "template_type": "professional",
        }

        with pytest.MonkeyPatch().context() as m:
            mock_deck_query = MagicMock()
            mock_deck_query.get_deck_status.return_value = None
            m.setattr(
                "app.api.v1.slides.operations.DeckQueries",
                lambda session: mock_deck_query,
            )

            response = client.post(
                f"/api/v1/decks/{deck_id}/slides",
                json=request_data,
                headers=auth_headers,
            )

        assert response.status_code == 404

    def test_insert_slide_unauthorized(self, client, mock_dependencies):
        """Test slide insertion without authentication."""
        deck_id = "12345678-1234-5678-9012-123456789012"

        request_data = {
            "position": 1,
            "seed_outline": "Test content",
            "template_type": "professional",
        }

        response = client.post(
            f"/api/v1/decks/{deck_id}/slides",
            json=request_data,
        )
        assert response.status_code == 401

    def test_insert_slide_reference_not_found(
        self, client, mock_dependencies, auth_headers
    ):
        """Test slide insertion with invalid after_slide_id reference."""
        deck_id = "12345678-1234-5678-9012-123456789012"

        request_data = {
            "after_slide_id": "non_existent_slide",
            "seed_outline": "Test content",
            "template_type": "professional",
        }

        # Mock deck verification
        mock_deck_info = {"deck_id": deck_id, "status": "editing"}

        # Mock existing slides (without the referenced slide)
        mock_existing_slides = [
            MagicMock(id="slide_1", order=1),
            MagicMock(id="slide_2", order=2),
        ]

        with pytest.MonkeyPatch().context() as m:
            mock_deck_query = MagicMock()
            mock_deck_query.get_deck_status.return_value = mock_deck_info
            m.setattr(
                "app.api.v1.slides.operations.DeckQueries",
                lambda session: mock_deck_query,
            )

            mock_slide_repo = AsyncMock()
            mock_slide_repo.get_by_deck_id.return_value = mock_existing_slides
            m.setattr(
                "app.api.v1.slides.operations.SlideRepository",
                lambda session: mock_slide_repo,
            )

            response = client.post(
                f"/api/v1/decks/{deck_id}/slides",
                json=request_data,
                headers=auth_headers,
            )

        assert response.status_code == 404
        assert "Reference slide not found" in response.json()["detail"]
