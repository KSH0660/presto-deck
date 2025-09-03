"""
Tests for deck status endpoints.
"""

import pytest
from unittest.mock import MagicMock


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
            m.setattr("app.api.v1.decks.status.DeckQueries", lambda session: mock_query)

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
            m.setattr("app.api.v1.decks.status.DeckQueries", lambda session: mock_query)

            response = client.get(
                f"/api/v1/decks/{deck_id}/status", headers=auth_headers
            )

        assert response.status_code == 404

    def test_get_deck_status_unauthorized(self, client, mock_dependencies):
        """Test deck status without authentication."""
        deck_id = "12345678-1234-5678-9012-123456789012"

        response = client.get(f"/api/v1/decks/{deck_id}/status")
        assert response.status_code == 401


class TestDeckDetails:
    """Test deck details endpoint GET /api/v1/decks/{deck_id}."""

    def test_get_deck_details_success(self, client, mock_dependencies, auth_headers):
        """Test successful deck details retrieval."""
        deck_id = "12345678-1234-5678-9012-123456789012"

        # Mock deck details response
        mock_deck_details = {
            "deck_id": deck_id,
            "status": "completed",
            "slides": [
                {"id": "slide_1", "title": "Introduction", "order": 1},
                {"id": "slide_2", "title": "Content", "order": 2},
            ],
            "created_at": "2023-12-01T10:00:00Z",
            "completed_at": "2023-12-01T11:00:00Z",
        }

        with pytest.MonkeyPatch().context() as m:
            mock_query = MagicMock()
            mock_query.get_deck_with_slides.return_value = mock_deck_details
            m.setattr("app.api.v1.decks.status.DeckQueries", lambda session: mock_query)

            response = client.get(f"/api/v1/decks/{deck_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["deck_id"] == deck_id
        assert data["status"] == "completed"
        assert "slides" in data

    def test_get_deck_details_not_found(self, client, mock_dependencies, auth_headers):
        """Test deck details for non-existent deck."""
        deck_id = "00000000-0000-0000-0000-000000000000"

        with pytest.MonkeyPatch().context() as m:
            mock_query = MagicMock()
            mock_query.get_deck_with_slides.return_value = None
            m.setattr("app.api.v1.decks.status.DeckQueries", lambda session: mock_query)

            response = client.get(f"/api/v1/decks/{deck_id}", headers=auth_headers)

        assert response.status_code == 404

    def test_get_deck_details_unauthorized(self, client, mock_dependencies):
        """Test deck details without authentication."""
        deck_id = "12345678-1234-5678-9012-123456789012"

        response = client.get(f"/api/v1/decks/{deck_id}")
        assert response.status_code == 401
