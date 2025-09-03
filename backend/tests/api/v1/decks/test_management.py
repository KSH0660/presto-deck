"""
Tests for deck management endpoints.
"""

import pytest
from unittest.mock import MagicMock


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
            m.setattr(
                "app.api.v1.decks.management.DeckQueries",
                lambda session: mock_deck_query,
            )

            # Redis client mock with setex
            class _FakeRedis:
                async def setex(self, *args, **kwargs):
                    return True

            async def _fake_get_redis_client():
                return _FakeRedis()

            m.setattr(
                "app.api.v1.decks.management.get_redis_client", _fake_get_redis_client
            )

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
            m.setattr(
                "app.api.v1.decks.management.DeckQueries",
                lambda session: mock_deck_query,
            )

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
            m.setattr(
                "app.api.v1.decks.management.DeckQueries",
                lambda session: mock_deck_query,
            )

            res = client.post(f"/api/v1/decks/{deck_id}/cancel", headers=auth_headers)

        assert res.status_code == 400

    def test_cancel_deck_unauthorized(self, client, mock_dependencies):
        deck_id = "12345678-1234-5678-9012-123456789012"

        res = client.post(f"/api/v1/decks/{deck_id}/cancel")
        assert res.status_code == 401
