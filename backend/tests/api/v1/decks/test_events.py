"""
Tests for deck events endpoint.
"""

import pytest
from unittest.mock import MagicMock


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
            m.setattr(
                "app.api.v1.decks.events.DeckQueries", lambda session: mock_deck_query
            )

            response = client.get(
                f"/api/v1/decks/{deck_id}/events", headers=auth_headers
            )

        assert response.status_code == 200
        # Currently returns empty list as per implementation
        data = response.json()
        assert isinstance(data, list)

    def test_get_deck_events_with_version(
        self, client, mock_dependencies, auth_headers
    ):
        """Test deck events with since_version parameter."""
        deck_id = "12345678-1234-5678-9012-123456789012"

        mock_deck_info = {"deck_id": deck_id, "status": "completed"}

        with pytest.MonkeyPatch().context() as m:
            mock_deck_query = MagicMock()
            mock_deck_query.get_deck_status.return_value = mock_deck_info
            m.setattr(
                "app.api.v1.decks.events.DeckQueries", lambda session: mock_deck_query
            )

            response = client.get(
                f"/api/v1/decks/{deck_id}/events?since_version=5&limit=10",
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_deck_events_not_found(self, client, mock_dependencies, auth_headers):
        """Test deck events for non-existent deck."""
        deck_id = "00000000-0000-0000-0000-000000000000"

        with pytest.MonkeyPatch().context() as m:
            mock_deck_query = MagicMock()
            mock_deck_query.get_deck_status.return_value = None
            m.setattr(
                "app.api.v1.decks.events.DeckQueries", lambda session: mock_deck_query
            )

            response = client.get(
                f"/api/v1/decks/{deck_id}/events", headers=auth_headers
            )

        assert response.status_code == 404

    def test_get_deck_events_unauthorized(self, client, mock_dependencies):
        """Test deck events without authentication."""
        deck_id = "12345678-1234-5678-9012-123456789012"

        response = client.get(f"/api/v1/decks/{deck_id}/events")
        assert response.status_code == 401
