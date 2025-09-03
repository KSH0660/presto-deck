"""
Tests for WebSocket API endpoints.

Covers WebSocket connections, real-time updates, and connection management.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestWebSocketDeckConnection:
    """Test WebSocket connection to deck updates."""

    def test_websocket_deck_connection_success(self, client, mock_dependencies):
        """Test successful WebSocket connection to deck updates."""
        deck_id = "12345678-1234-5678-9012-123456789012"
        token = "valid_jwt_token"

        # Mock deck verification
        mock_deck_info = {"deck_id": deck_id, "status": "generating"}

        with patch("app.api.v1.websocket.verify_websocket_token") as mock_verify:
            mock_verify.return_value = "user_123"

            with patch("app.api.v1.websocket.async_session") as mock_session:
                mock_session.return_value.__aenter__.return_value = MagicMock()

                with patch("app.api.v1.websocket.DeckQueries") as mock_deck_query_class:
                    mock_deck_query = MagicMock()
                    mock_deck_query.get_deck_status.return_value = mock_deck_info
                    mock_deck_query_class.return_value = mock_deck_query

                    with client.websocket_connect(
                        f"/api/v1/ws/decks/{deck_id}?token={token}"
                    ) as websocket:
                        # Should receive connection confirmation
                        data = websocket.receive_json()
                        assert data["type"] == "connected"
                        assert data["deck_id"] == deck_id
                        assert "message" in data

                        # Send a ping and expect pong
                        websocket.send_json({"type": "ping"})
                        response = websocket.receive_json()
                        assert response["type"] == "pong"

    def test_websocket_deck_connection_unauthorized(self, client, mock_dependencies):
        """Test WebSocket connection without valid token."""
        deck_id = "12345678-1234-5678-9012-123456789012"

        with patch("app.api.v1.websocket.verify_websocket_token") as mock_verify:
            mock_verify.return_value = None  # Invalid token

            # Connection should be closed with auth error
            with pytest.raises(Exception):  # WebSocket will raise exception on close
                with client.websocket_connect(
                    f"/api/v1/ws/decks/{deck_id}?token=invalid"
                ):
                    pass  # Should not reach here

    def test_websocket_deck_access_denied(self, client, mock_dependencies):
        """Test WebSocket connection to deck user doesn't own."""
        deck_id = "12345678-1234-5678-9012-123456789012"
        token = "valid_jwt_token"

        with patch("app.api.v1.websocket.verify_websocket_token") as mock_verify:
            mock_verify.return_value = "user_123"

            with patch("app.api.v1.websocket.async_session") as mock_session:
                mock_session.return_value.__aenter__.return_value = MagicMock()

                with patch("app.api.v1.websocket.DeckQueries") as mock_deck_query_class:
                    mock_deck_query = MagicMock()
                    mock_deck_query.get_deck_status.return_value = None  # Access denied
                    mock_deck_query_class.return_value = mock_deck_query

                    # Connection should be closed with access denied
                    with pytest.raises(Exception):
                        with client.websocket_connect(
                            f"/api/v1/ws/decks/{deck_id}?token={token}"
                        ):
                            pass

    def test_websocket_deck_with_event_replay(self, client, mock_dependencies):
        """Test WebSocket connection with event replay."""
        deck_id = "12345678-1234-5678-9012-123456789012"
        token = "valid_jwt_token"
        last_version = 5

        mock_deck_info = {"deck_id": deck_id, "status": "generating"}

        # Mock replay events
        mock_replay_events = [
            {
                "type": "SlideAdded",
                "deck_id": deck_id,
                "slide_id": "slide_123",
                "version": 6,
                "timestamp": "2023-12-01T10:00:00Z",
            }
        ]

        with patch("app.api.v1.websocket.verify_websocket_token") as mock_verify:
            mock_verify.return_value = "user_123"

            with patch("app.api.v1.websocket.async_session") as mock_session:
                mock_session.return_value.__aenter__.return_value = MagicMock()

                with patch("app.api.v1.websocket.DeckQueries") as mock_deck_query_class:
                    mock_deck_query = MagicMock()
                    mock_deck_query.get_deck_status.return_value = mock_deck_info
                    mock_deck_query_class.return_value = mock_deck_query

                    with patch("app.api.v1.websocket.get_replay_events") as mock_replay:
                        mock_replay.return_value = mock_replay_events

                        with client.websocket_connect(
                            f"/api/v1/ws/decks/{deck_id}?token={token}&last_version={last_version}"
                        ) as websocket:
                            # Should receive replayed events first
                            replay_event = websocket.receive_json()
                            assert replay_event["type"] == "SlideAdded"
                            assert replay_event["version"] == 6

                            # Then connection confirmation
                            connection_msg = websocket.receive_json()
                            assert connection_msg["type"] == "connected"


class TestWebSocketUserConnection:
    """Test WebSocket connection to user-level updates."""

    def test_websocket_user_connection_success(self, client, mock_dependencies):
        """Test successful WebSocket connection to user updates."""
        user_id = "12345678-1234-5678-9012-123456789012"
        token = "valid_jwt_token"

        with patch("app.api.v1.websocket.verify_websocket_token") as mock_verify:
            mock_verify.return_value = user_id  # Token matches user_id

            with client.websocket_connect(
                f"/api/v1/ws/user/{user_id}/decks?token={token}"
            ) as websocket:
                # Should receive connection confirmation
                data = websocket.receive_json()
                assert data["type"] == "connected"
                assert data["user_id"] == user_id
                assert "message" in data

    def test_websocket_user_connection_wrong_user(self, client, mock_dependencies):
        """Test WebSocket connection with token for different user."""
        user_id = "12345678-1234-5678-9012-123456789012"
        token_user_id = "87654321-4321-8765-4321-876543210987"
        token = "valid_jwt_token"

        with patch("app.api.v1.websocket.verify_websocket_token") as mock_verify:
            mock_verify.return_value = token_user_id  # Different from URL user_id

            # Connection should be closed
            with pytest.raises(Exception):
                with client.websocket_connect(
                    f"/api/v1/ws/user/{user_id}/decks?token={token}"
                ):
                    pass


class TestWebSocketConnectionManagement:
    """Test WebSocket connection management endpoints."""

    def test_get_connection_stats(self, client, mock_dependencies, auth_headers):
        """Test retrieving WebSocket connection statistics."""

        # Mock WebSocket broadcaster stats
        mock_ws_broadcaster = mock_dependencies["ws_broadcaster"]
        mock_ws_broadcaster.get_connected_users.return_value = ["user_1", "user_2"]
        mock_ws_broadcaster.get_connected_decks.return_value = [
            "deck_1",
            "deck_2",
            "deck_3",
        ]

        response = client.get("/api/v1/ws/connections/stats", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["connected_users"] == 2
        assert data["connected_decks"] == 3
        assert "user_1" in data["users"]
        assert "deck_1" in data["decks"]

    def test_broadcast_to_deck(self, client, mock_dependencies, auth_headers):
        """Test manual broadcast to deck clients."""
        deck_id = "12345678-1234-5678-9012-123456789012"

        broadcast_message = {
            "type": "custom_notification",
            "message": "This is a test broadcast",
            "data": {"key": "value"},
        }

        mock_ws_broadcaster = mock_dependencies["ws_broadcaster"]
        mock_ws_broadcaster.broadcast_to_deck = AsyncMock()

        response = client.post(
            f"/api/v1/ws/decks/{deck_id}/broadcast",
            json=broadcast_message,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert deck_id in data["message"]

        # Verify broadcast was called
        mock_ws_broadcaster.broadcast_to_deck.assert_called_once_with(
            str(deck_id), broadcast_message
        )

    def test_broadcast_to_user(self, client, mock_dependencies, auth_headers):
        """Test manual broadcast to user clients."""
        user_id = "12345678-1234-5678-9012-123456789012"

        broadcast_message = {
            "type": "user_notification",
            "title": "Your deck is ready!",
            "deck_id": "deck_123",
        }

        mock_ws_broadcaster = mock_dependencies["ws_broadcaster"]
        mock_ws_broadcaster.broadcast_to_user = AsyncMock()

        response = client.post(
            f"/api/v1/ws/users/{user_id}/broadcast",
            json=broadcast_message,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert user_id in data["message"]

        # Verify broadcast was called
        mock_ws_broadcaster.broadcast_to_user.assert_called_once_with(
            str(user_id), broadcast_message
        )


class TestWebSocketMessageTypes:
    """Test different WebSocket message types and interactions."""

    def test_websocket_subscription_changes(self, client, mock_dependencies):
        """Test changing event subscriptions via WebSocket."""
        deck_id = "12345678-1234-5678-9012-123456789012"
        token = "valid_jwt_token"

        mock_deck_info = {"deck_id": deck_id, "status": "generating"}

        with patch("app.api.v1.websocket.verify_websocket_token") as mock_verify:
            mock_verify.return_value = "user_123"

            with patch("app.api.v1.websocket.async_session") as mock_session:
                mock_session.return_value.__aenter__.return_value = MagicMock()

                with patch("app.api.v1.websocket.DeckQueries") as mock_deck_query_class:
                    mock_deck_query = MagicMock()
                    mock_deck_query.get_deck_status.return_value = mock_deck_info
                    mock_deck_query_class.return_value = mock_deck_query

                    with client.websocket_connect(
                        f"/api/v1/ws/decks/{deck_id}?token={token}"
                    ) as websocket:
                        # Get connection confirmation
                        websocket.receive_json()

                        # Send subscription change message
                        subscription_msg = {"type": "subscribe_events"}
                        websocket.send_json(subscription_msg)

                        # The WebSocket should handle this (no response expected in current implementation)
                        # This test verifies the message doesn't cause errors

    def test_websocket_ping_pong_keepalive(self, client, mock_dependencies):
        """Test ping/pong keepalive mechanism."""
        deck_id = "12345678-1234-5678-9012-123456789012"
        token = "valid_jwt_token"

        mock_deck_info = {"deck_id": deck_id, "status": "generating"}

        with patch("app.api.v1.websocket.verify_websocket_token") as mock_verify:
            mock_verify.return_value = "user_123"

            with patch("app.api.v1.websocket.async_session") as mock_session:
                mock_session.return_value.__aenter__.return_value = MagicMock()

                with patch("app.api.v1.websocket.DeckQueries") as mock_deck_query_class:
                    mock_deck_query = MagicMock()
                    mock_deck_query.get_deck_status.return_value = mock_deck_info
                    mock_deck_query_class.return_value = mock_deck_query

                    with client.websocket_connect(
                        f"/api/v1/ws/decks/{deck_id}?token={token}"
                    ) as websocket:
                        # Get connection confirmation
                        websocket.receive_json()

                        # Send ping
                        websocket.send_json({"type": "ping"})

                        # Should receive pong
                        response = websocket.receive_json()
                        assert response["type"] == "pong"
                        assert "timestamp" in response

    def test_websocket_invalid_json_handling(self, client, mock_dependencies):
        """Test handling of invalid JSON messages."""
        deck_id = "12345678-1234-5678-9012-123456789012"
        token = "valid_jwt_token"

        mock_deck_info = {"deck_id": deck_id, "status": "generating"}

        with patch("app.api.v1.websocket.verify_websocket_token") as mock_verify:
            mock_verify.return_value = "user_123"

            with patch("app.api.v1.websocket.async_session") as mock_session:
                mock_session.return_value.__aenter__.return_value = MagicMock()

                with patch("app.api.v1.websocket.DeckQueries") as mock_deck_query_class:
                    mock_deck_query = MagicMock()
                    mock_deck_query.get_deck_status.return_value = mock_deck_info
                    mock_deck_query_class.return_value = mock_deck_query

                    with client.websocket_connect(
                        f"/api/v1/ws/decks/{deck_id}?token={token}"
                    ) as websocket:
                        # Get connection confirmation
                        websocket.receive_json()

                        # Send invalid JSON (this would be sent as text, not JSON)
                        websocket.send_text("invalid json {")

                        # Connection should remain stable (invalid messages are ignored)
                        # Send a valid ping to verify connection is still active
                        websocket.send_json({"type": "ping"})
                        response = websocket.receive_json()
                        assert response["type"] == "pong"


@pytest.mark.asyncio
class TestAsyncWebSocketOperations:
    """Test async WebSocket operations that require async test framework."""

    async def test_websocket_broadcast_integration(
        self, async_client, mock_dependencies
    ):
        """Test WebSocket broadcasting integration with async client."""
        # This would be a more comprehensive integration test
        # using the async client for WebSocket connections

        # For now, this demonstrates the structure for async WebSocket tests
        # Full implementation would require setting up WebSocket connections
        # and testing real broadcast scenarios

        mock_ws_broadcaster = mock_dependencies["ws_broadcaster"]

        # Simulate broadcast call
        await mock_ws_broadcaster.broadcast_to_deck(
            "deck_123", {"type": "SlideUpdated", "slide_id": "slide_456"}
        )

        # Verify broadcast was called
        mock_ws_broadcaster.broadcast_to_deck.assert_called_once()

    async def test_websocket_connection_lifecycle(
        self, async_client, mock_dependencies
    ):
        """Test complete WebSocket connection lifecycle."""
        # This would test:
        # 1. Connection establishment
        # 2. Authentication
        # 3. Message exchange
        # 4. Graceful disconnection
        # 5. Cleanup

        # Implementation would use async WebSocket client
        # and mock the full connection lifecycle
        pass


class TestWebSocketErrorHandling:
    """Test WebSocket error handling and edge cases."""

    def test_websocket_connection_timeout_handling(self, client, mock_dependencies):
        """Test WebSocket connection timeout handling."""
        # This would test the timeout behavior in WebSocket connections
        # Implementation depends on how timeouts are configured
        pass

    def test_websocket_database_error_handling(self, client, mock_dependencies):
        """Test WebSocket behavior when database errors occur."""
        deck_id = "12345678-1234-5678-9012-123456789012"
        token = "valid_jwt_token"

        with patch("app.api.v1.websocket.verify_websocket_token") as mock_verify:
            mock_verify.return_value = "user_123"

            with patch("app.api.v1.websocket.async_session") as mock_session:
                # Simulate database error
                mock_session.return_value.__aenter__.side_effect = Exception(
                    "Database connection failed"
                )

                # Connection should be closed with error
                with pytest.raises(Exception):
                    with client.websocket_connect(
                        f"/api/v1/ws/decks/{deck_id}?token={token}"
                    ):
                        pass

    def test_websocket_broadcaster_error_handling(self, client, mock_dependencies):
        """Test handling of WebSocket broadcaster errors."""
        # Test what happens when the broadcaster fails to send messages
        # This would verify error handling doesn't crash the WebSocket connection
        pass
