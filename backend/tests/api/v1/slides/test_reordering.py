"""
Tests for slide reordering endpoint.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock


class TestSlideReordering:
    """Test slide reordering endpoint POST /api/v1/decks/{deck_id}/reorder."""

    def test_reorder_slides_success(self, client, mock_dependencies, auth_headers):
        """Test successful slide reordering."""
        deck_id = "12345678-1234-5678-9012-123456789012"

        request_data = {
            "orders": [
                {"slide_id": "slide_1", "order": 3},
                {"slide_id": "slide_2", "order": 1},
                {"slide_id": "slide_3", "order": 2},
            ]
        }

        # Mock deck verification
        mock_deck_info = {"deck_id": deck_id, "status": "editing"}

        # Mock existing slides
        mock_existing_slides = [
            MagicMock(id="slide_1", order=1),
            MagicMock(id="slide_2", order=2),
            MagicMock(id="slide_3", order=3),
        ]

        # Mock updated slides (after reordering)
        mock_updated_slides = [
            MagicMock(
                id="slide_2",
                order=1,
                deck_id=deck_id,
                title="Slide 2",
                content_outline="Content 2",
                html_content="<h1>Slide 2</h1>",
                presenter_notes="Notes 2",
                template_filename="professional",
                created_at="2023-12-01T10:00:00Z",
                updated_at="2023-12-01T10:30:00Z",
            ),
            MagicMock(
                id="slide_3",
                order=2,
                deck_id=deck_id,
                title="Slide 3",
                content_outline="Content 3",
                html_content="<h1>Slide 3</h1>",
                presenter_notes="Notes 3",
                template_filename="professional",
                created_at="2023-12-01T10:00:00Z",
                updated_at="2023-12-01T10:30:00Z",
            ),
            MagicMock(
                id="slide_1",
                order=3,
                deck_id=deck_id,
                title="Slide 1",
                content_outline="Content 1",
                html_content="<h1>Slide 1</h1>",
                presenter_notes="Notes 1",
                template_filename="professional",
                created_at="2023-12-01T10:00:00Z",
                updated_at="2023-12-01T10:30:00Z",
            ),
        ]

        with pytest.MonkeyPatch().context() as m:
            mock_deck_query = MagicMock()
            mock_deck_query.get_deck_status.return_value = mock_deck_info
            m.setattr(
                "app.api.v1.slides.reordering.DeckQueries",
                lambda session: mock_deck_query,
            )

            mock_slide_repo = AsyncMock()
            mock_slide_repo.get_by_deck_id.side_effect = [
                mock_existing_slides,
                mock_updated_slides,
            ]
            mock_slide_repo.update = AsyncMock()
            m.setattr(
                "app.api.v1.slides.reordering.SlideRepository",
                lambda session: mock_slide_repo,
            )

            response = client.post(
                f"/api/v1/decks/{deck_id}/reorder",
                json=request_data,
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 3
        # Verify the new order
        assert data["items"][0]["id"] == "slide_2"
        assert data["items"][1]["id"] == "slide_3"
        assert data["items"][2]["id"] == "slide_1"

    def test_reorder_slides_deck_not_found(
        self, client, mock_dependencies, auth_headers
    ):
        """Test slide reordering for non-existent deck."""
        deck_id = "00000000-0000-0000-0000-000000000000"

        request_data = {
            "orders": [
                {"slide_id": "slide_1", "order": 1},
            ]
        }

        with pytest.MonkeyPatch().context() as m:
            mock_deck_query = MagicMock()
            mock_deck_query.get_deck_status.return_value = None
            m.setattr(
                "app.api.v1.slides.reordering.DeckQueries",
                lambda session: mock_deck_query,
            )

            response = client.post(
                f"/api/v1/decks/{deck_id}/reorder",
                json=request_data,
                headers=auth_headers,
            )

        assert response.status_code == 404

    def test_reorder_slides_slide_not_found(
        self, client, mock_dependencies, auth_headers
    ):
        """Test slide reordering with non-existent slide ID."""
        deck_id = "12345678-1234-5678-9012-123456789012"

        request_data = {
            "orders": [
                {"slide_id": "non_existent_slide", "order": 1},
            ]
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
                "app.api.v1.slides.reordering.DeckQueries",
                lambda session: mock_deck_query,
            )

            mock_slide_repo = AsyncMock()
            mock_slide_repo.get_by_deck_id.return_value = mock_existing_slides
            m.setattr(
                "app.api.v1.slides.reordering.SlideRepository",
                lambda session: mock_slide_repo,
            )

            response = client.post(
                f"/api/v1/decks/{deck_id}/reorder",
                json=request_data,
                headers=auth_headers,
            )

        assert response.status_code == 404
        assert "Slide non_existent_slide not found" in response.json()["detail"]

    def test_reorder_slides_unauthorized(self, client, mock_dependencies):
        """Test slide reordering without authentication."""
        deck_id = "12345678-1234-5678-9012-123456789012"

        request_data = {
            "orders": [
                {"slide_id": "slide_1", "order": 1},
            ]
        }

        response = client.post(
            f"/api/v1/decks/{deck_id}/reorder",
            json=request_data,
        )
        assert response.status_code == 401

    def test_reorder_slides_empty_orders(self, client, mock_dependencies, auth_headers):
        """Test slide reordering with empty orders list."""
        deck_id = "12345678-1234-5678-9012-123456789012"

        request_data = {"orders": []}

        # Mock deck verification
        mock_deck_info = {"deck_id": deck_id, "status": "editing"}

        with pytest.MonkeyPatch().context() as m:
            mock_deck_query = MagicMock()
            mock_deck_query.get_deck_status.return_value = mock_deck_info
            m.setattr(
                "app.api.v1.slides.reordering.DeckQueries",
                lambda session: mock_deck_query,
            )

            mock_slide_repo = AsyncMock()
            mock_slide_repo.get_by_deck_id.return_value = []
            m.setattr(
                "app.api.v1.slides.reordering.SlideRepository",
                lambda session: mock_slide_repo,
            )

            response = client.post(
                f"/api/v1/decks/{deck_id}/reorder",
                json=request_data,
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
