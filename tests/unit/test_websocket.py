"""Unit tests for WebSocket handlers."""

import asyncio
import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.api.schemas import Event
from app.api.websocket import (
    WebSocketManager,
    _handle_client_message,
    _send_event_replay,
)
from app.domain.entities import Deck, DeckStatus, DeckEvent
from app.domain.exceptions import DeckNotFoundException, UnauthorizedAccessException


class TestWebSocketManager:
    """Test cases for WebSocketManager."""

    @pytest.fixture
    def mock_redis_pubsub(self):
        """Create mock Redis PubSub manager."""
        return AsyncMock()

    @pytest.fixture
    def ws_manager(self, mock_redis_pubsub):
        """Create WebSocket manager instance."""
        return WebSocketManager(mock_redis_pubsub)

    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket."""
        ws = Mock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        ws.client_state = WebSocketState.CONNECTED
        return ws

    @pytest.mark.asyncio
    async def test_connect_first_connection(
        self, ws_manager, mock_websocket, mock_redis_pubsub
    ):
        """Test connecting the first WebSocket for a deck."""
        deck_id = uuid4()
        user_id = "test-user-123"

        with patch(
            "app.api.websocket.metrics.record_websocket_connection"
        ) as mock_metrics:
            await ws_manager.connect(mock_websocket, deck_id, user_id)

        # Assertions
        mock_websocket.accept.assert_called_once()
        assert deck_id in ws_manager.active_connections
        assert mock_websocket in ws_manager.active_connections[deck_id]
        assert deck_id in ws_manager._consumers
        assert isinstance(ws_manager._consumers[deck_id], asyncio.Task)
        mock_metrics.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_connect_additional_connection(self, ws_manager, mock_redis_pubsub):
        """Test connecting additional WebSocket for existing deck."""
        deck_id = uuid4()
        user_id = "test-user-123"

        # Setup existing connection
        first_ws = Mock(spec=WebSocket)
        first_ws.accept = AsyncMock()
        first_ws.client_state = WebSocketState.CONNECTED
        ws_manager.active_connections[deck_id] = {first_ws}
        ws_manager._consumers[deck_id] = Mock()

        # Connect second WebSocket
        second_ws = Mock(spec=WebSocket)
        second_ws.accept = AsyncMock()
        second_ws.client_state = WebSocketState.CONNECTED

        consumer_count_before = len(ws_manager._consumers)

        await ws_manager.connect(second_ws, deck_id, user_id)

        # Assertions
        second_ws.accept.assert_called_once()
        assert len(ws_manager.active_connections[deck_id]) == 2
        assert second_ws in ws_manager.active_connections[deck_id]
        # Should not create a new consumer
        assert len(ws_manager._consumers) == consumer_count_before

    @pytest.mark.asyncio
    async def test_disconnect_last_connection(self, ws_manager, mock_websocket):
        """Test disconnecting the last WebSocket for a deck."""
        deck_id = uuid4()

        # Setup existing connection
        mock_consumer = Mock()
        mock_consumer.cancel = Mock()
        ws_manager.active_connections[deck_id] = {mock_websocket}
        ws_manager._consumers[deck_id] = mock_consumer

        with patch(
            "app.api.websocket.metrics.record_websocket_connection"
        ) as mock_metrics:
            await ws_manager.disconnect(mock_websocket, deck_id)

        # Assertions
        assert deck_id not in ws_manager.active_connections
        assert deck_id not in ws_manager._consumers
        mock_consumer.cancel.assert_called_once()
        mock_metrics.assert_called_once_with(-1)

    @pytest.mark.asyncio
    async def test_disconnect_partial_connection(self, ws_manager):
        """Test disconnecting one of multiple WebSockets for a deck."""
        deck_id = uuid4()

        # Setup multiple connections
        ws1 = Mock(spec=WebSocket)
        ws2 = Mock(spec=WebSocket)
        mock_consumer = Mock()
        ws_manager.active_connections[deck_id] = {ws1, ws2}
        ws_manager._consumers[deck_id] = mock_consumer

        await ws_manager.disconnect(ws1, deck_id)

        # Assertions
        assert deck_id in ws_manager.active_connections
        assert ws1 not in ws_manager.active_connections[deck_id]
        assert ws2 in ws_manager.active_connections[deck_id]
        assert deck_id in ws_manager._consumers
        # Consumer should not be cancelled
        mock_consumer.cancel.assert_not_called()

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_connection(self, ws_manager, mock_websocket):
        """Test disconnecting WebSocket that doesn't exist."""
        deck_id = uuid4()

        # Should not raise exception
        with patch(
            "app.api.websocket.metrics.record_websocket_connection"
        ) as mock_metrics:
            await ws_manager.disconnect(mock_websocket, deck_id)

        mock_metrics.assert_called_once_with(-1)

    @pytest.mark.asyncio
    async def test_send_personal_message_connected(self, ws_manager, mock_websocket):
        """Test sending personal message to connected WebSocket."""
        message = "test message"

        await ws_manager.send_personal_message(message, mock_websocket)

        mock_websocket.send_text.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_send_personal_message_disconnected(self, ws_manager):
        """Test sending personal message to disconnected WebSocket."""
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.client_state = WebSocketState.DISCONNECTED
        mock_websocket.send_text = AsyncMock()

        await ws_manager.send_personal_message("test", mock_websocket)

        # Should not attempt to send
        mock_websocket.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcast_to_deck_success(self, ws_manager):
        """Test successful broadcasting to deck connections."""
        deck_id = uuid4()
        message = "broadcast message"

        # Setup multiple connections
        ws1 = Mock(spec=WebSocket)
        ws1.client_state = WebSocketState.CONNECTED
        ws1.send_text = AsyncMock()

        ws2 = Mock(spec=WebSocket)
        ws2.client_state = WebSocketState.CONNECTED
        ws2.send_text = AsyncMock()

        ws_manager.active_connections[deck_id] = {ws1, ws2}

        await ws_manager.broadcast_to_deck(deck_id, message)

        # Assertions
        ws1.send_text.assert_called_once_with(message)
        ws2.send_text.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_broadcast_to_deck_with_failed_connection(self, ws_manager):
        """Test broadcasting with one failed connection."""
        deck_id = uuid4()
        message = "broadcast message"

        # Setup connections - one good, one bad
        good_ws = Mock(spec=WebSocket)
        good_ws.client_state = WebSocketState.CONNECTED
        good_ws.send_text = AsyncMock()

        bad_ws = Mock(spec=WebSocket)
        bad_ws.client_state = WebSocketState.CONNECTED
        bad_ws.send_text = AsyncMock(side_effect=Exception("Connection failed"))

        ws_manager.active_connections[deck_id] = {good_ws, bad_ws}

        with patch.object(ws_manager, "disconnect", AsyncMock()) as mock_disconnect:
            await ws_manager.broadcast_to_deck(deck_id, message)

        # Assertions
        good_ws.send_text.assert_called_once_with(message)
        bad_ws.send_text.assert_called_once_with(message)
        mock_disconnect.assert_called_once_with(bad_ws, deck_id)

    @pytest.mark.asyncio
    async def test_broadcast_to_nonexistent_deck(self, ws_manager):
        """Test broadcasting to deck with no connections."""
        deck_id = uuid4()

        # Should not raise exception
        await ws_manager.broadcast_to_deck(deck_id, "message")

    @pytest.mark.asyncio
    async def test_consume_deck_events(self, ws_manager, mock_redis_pubsub):
        """Test consuming deck events from Redis."""
        deck_id = uuid4()

        # Create mock events
        event1 = Event(
            event_type="SlideAdded",
            deck_id=deck_id,
            version=1,
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
            payload={"slide_id": "123"},
        )

        event2 = Event(
            event_type="DeckCompleted",
            deck_id=deck_id,
            version=2,
            timestamp=datetime(2024, 1, 1, 10, 1, 0),
            payload={},
        )

        # Track calls to subscription method
        call_deck_id = None

        # Mock Redis subscription - make the method itself an async generator
        async def mock_subscribe(deck_id):
            nonlocal call_deck_id
            call_deck_id = deck_id
            yield event1
            yield event2
            raise asyncio.CancelledError()  # Simulate cancellation

        mock_redis_pubsub.subscribe_to_deck_channel = mock_subscribe

        # Mock broadcast method
        ws_manager.broadcast_to_deck = AsyncMock()

        # Test event consumption
        await ws_manager._consume_deck_events(deck_id)

        # Assertions
        assert call_deck_id == deck_id  # Verify correct deck_id was passed
        assert ws_manager.broadcast_to_deck.call_count == 2

        # Check first broadcast call
        first_call = ws_manager.broadcast_to_deck.call_args_list[0]
        assert first_call[0][0] == deck_id
        message1 = json.loads(first_call[0][1])
        assert message1["type"] == "event"
        assert message1["data"]["event_type"] == "SlideAdded"
        assert message1["data"]["version"] == 1

        # Check second broadcast call
        second_call = ws_manager.broadcast_to_deck.call_args_list[1]
        message2 = json.loads(second_call[0][1])
        assert message2["data"]["event_type"] == "DeckCompleted"
        assert message2["data"]["version"] == 2

    @pytest.mark.asyncio
    async def test_consume_deck_events_error(self, ws_manager, mock_redis_pubsub):
        """Test event consumption with Redis error."""
        deck_id = uuid4()

        # Mock Redis subscription to raise error
        mock_redis_pubsub.subscribe_to_deck_channel.side_effect = Exception(
            "Redis error"
        )

        # Should not raise exception
        await ws_manager._consume_deck_events(deck_id)

        mock_redis_pubsub.subscribe_to_deck_channel.assert_called_once_with(deck_id)


class TestWebSocketEndpoint:
    """Test cases for WebSocket endpoint functionality."""

    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket."""
        ws = Mock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        ws.receive_text = AsyncMock()
        ws.close = AsyncMock()
        ws.client_state = WebSocketState.CONNECTED
        return ws

    @pytest.fixture
    def mock_deck_service(self):
        """Create mock deck service."""
        service = AsyncMock()
        service.get_deck.return_value = Deck(
            id=uuid4(),
            user_id="test-user-123",
            title="Test Deck",
            status=DeckStatus.PENDING,
        )
        return service

    @pytest.fixture
    def mock_slide_service(self):
        """Create mock slide service."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_websocket_endpoint_authentication_failure(self, mock_websocket):
        """Test WebSocket endpoint with invalid token."""
        deck_id = uuid4()

        with patch(
            "app.api.websocket.security_service.extract_user_id_from_token",
            side_effect=Exception("Invalid token"),
        ):
            from app.api.websocket import websocket_endpoint

            await websocket_endpoint(
                websocket=mock_websocket,
                deck_id=deck_id,
                token="invalid-token",
                deck_service=AsyncMock(),
                slide_service=AsyncMock(),
            )

        # WebSocket should be closed
        mock_websocket.close.assert_called()

    @pytest.mark.asyncio
    async def test_websocket_endpoint_deck_not_found(
        self, mock_websocket, mock_deck_service
    ):
        """Test WebSocket endpoint when deck not found."""
        deck_id = uuid4()
        mock_deck_service.get_deck.side_effect = DeckNotFoundException("Deck not found")

        with patch(
            "app.api.websocket.security_service.extract_user_id_from_token",
            return_value="test-user-123",
        ):
            from app.api.websocket import websocket_endpoint

            await websocket_endpoint(
                websocket=mock_websocket,
                deck_id=deck_id,
                token="valid-token",
                deck_service=mock_deck_service,
                slide_service=AsyncMock(),
            )

        # WebSocket should be closed with specific code
        mock_websocket.close.assert_called_with(
            code=4003, reason="Deck with ID Deck not found not found"
        )

    @pytest.mark.asyncio
    async def test_websocket_endpoint_unauthorized_access(
        self, mock_websocket, mock_deck_service
    ):
        """Test WebSocket endpoint when user unauthorized."""
        deck_id = uuid4()
        mock_deck_service.get_deck.side_effect = UnauthorizedAccessException(
            "Access denied"
        )

        with patch(
            "app.api.websocket.security_service.extract_user_id_from_token",
            return_value="test-user-123",
        ):
            from app.api.websocket import websocket_endpoint

            await websocket_endpoint(
                websocket=mock_websocket,
                deck_id=deck_id,
                token="valid-token",
                deck_service=mock_deck_service,
                slide_service=AsyncMock(),
            )

        mock_websocket.close.assert_called_with(
            code=4003, reason="User None is not authorized to access Access denied"
        )


class TestEventReplay:
    """Test cases for event replay functionality."""

    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket."""
        ws = Mock(spec=WebSocket)
        ws.send_text = AsyncMock()
        ws.client_state = WebSocketState.CONNECTED
        return ws

    @pytest.fixture
    def mock_connection_manager(self, mock_websocket):
        """Create mock connection manager."""
        manager = AsyncMock()
        manager.send_personal_message = AsyncMock()
        return manager

    @pytest.fixture
    def sample_events(self):
        """Create sample deck events for replay."""
        deck_id = uuid4()
        return [
            DeckEvent(
                id=1,
                deck_id=deck_id,
                version=1,
                event_type="DeckStarted",
                payload={"title": "Test Deck"},
                created_at=datetime(2024, 1, 1, 10, 0, 0),
            ),
            DeckEvent(
                id=2,
                deck_id=deck_id,
                version=2,
                event_type="SlideAdded",
                payload={"slide_id": "123", "order": 1},
                created_at=datetime(2024, 1, 1, 10, 1, 0),
            ),
        ]

    @pytest.mark.asyncio
    async def test_send_event_replay_success(self, mock_websocket, sample_events):
        """Test successful event replay."""
        deck_id = uuid4()
        user_id = "test-user-123"
        from_version = 0

        mock_deck_service = AsyncMock()
        mock_deck_service.get_deck_events.return_value = sample_events

        mock_connection_manager = AsyncMock()

        with patch("app.api.websocket.connection_manager", mock_connection_manager):
            await _send_event_replay(
                mock_websocket, mock_deck_service, deck_id, user_id, from_version
            )

        # Assertions
        mock_deck_service.get_deck_events.assert_called_once_with(
            deck_id, user_id, from_version
        )

        # Should send replay messages + complete message
        assert mock_connection_manager.send_personal_message.call_count == 3

        # Check replay messages
        calls = mock_connection_manager.send_personal_message.call_args_list

        # First event replay
        first_message = json.loads(calls[0][0][0])
        assert first_message["type"] == "replay"
        assert first_message["data"]["event_type"] == "DeckStarted"
        assert first_message["data"]["version"] == 1

        # Second event replay
        second_message = json.loads(calls[1][0][0])
        assert second_message["type"] == "replay"
        assert second_message["data"]["event_type"] == "SlideAdded"
        assert second_message["data"]["version"] == 2

        # Complete message
        complete_message = json.loads(calls[2][0][0])
        assert complete_message["type"] == "replay_complete"
        assert complete_message["data"]["replayed_events"] == 2

    @pytest.mark.asyncio
    async def test_send_event_replay_empty_events(self, mock_websocket):
        """Test event replay with no events."""
        deck_id = uuid4()
        user_id = "test-user-123"
        from_version = 0

        mock_deck_service = AsyncMock()
        mock_deck_service.get_deck_events.return_value = []

        mock_connection_manager = AsyncMock()

        with patch("app.api.websocket.connection_manager", mock_connection_manager):
            await _send_event_replay(
                mock_websocket, mock_deck_service, deck_id, user_id, from_version
            )

        # Should only send complete message
        assert mock_connection_manager.send_personal_message.call_count == 1

        complete_message = json.loads(
            mock_connection_manager.send_personal_message.call_args[0][0]
        )
        assert complete_message["type"] == "replay_complete"
        assert complete_message["data"]["replayed_events"] == 0

    @pytest.mark.asyncio
    async def test_send_event_replay_service_error(self, mock_websocket):
        """Test event replay with service error."""
        deck_id = uuid4()
        user_id = "test-user-123"
        from_version = 0

        mock_deck_service = AsyncMock()
        mock_deck_service.get_deck_events.side_effect = Exception("Service error")

        mock_connection_manager = AsyncMock()

        with patch("app.api.websocket.connection_manager", mock_connection_manager):
            await _send_event_replay(
                mock_websocket, mock_deck_service, deck_id, user_id, from_version
            )

        # Should send error message
        mock_connection_manager.send_personal_message.assert_called_once()
        error_message = json.loads(
            mock_connection_manager.send_personal_message.call_args[0][0]
        )
        assert error_message["type"] == "error"
        assert "Failed to replay events" in error_message["data"]["message"]


class TestClientMessageHandling:
    """Test cases for client message handling."""

    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket."""
        return Mock(spec=WebSocket)

    @pytest.mark.asyncio
    async def test_handle_slide_update_message(self, mock_websocket):
        """Test handling slide update message."""
        deck_id = uuid4()
        user_id = "test-user-123"
        slide_id = uuid4()

        message_data = json.dumps(
            {
                "type": "update_slide",
                "data": {
                    "slide_id": str(slide_id),
                    "prompt": "Make this slide more engaging",
                },
            }
        )

        mock_deck_service = AsyncMock()
        mock_slide_service = AsyncMock()
        mock_connection_manager = AsyncMock()

        with patch("app.api.websocket.connection_manager", mock_connection_manager):
            await _handle_client_message(
                mock_websocket,
                message_data,
                deck_id,
                user_id,
                mock_deck_service,
                mock_slide_service,
            )

        # Assertions
        mock_slide_service.update_slide.assert_called_once_with(
            slide_id, "Make this slide more engaging", user_id
        )

        mock_connection_manager.send_personal_message.assert_called_once()
        response_message = json.loads(
            mock_connection_manager.send_personal_message.call_args[0][0]
        )
        assert response_message["type"] == "slide_update_queued"
        assert response_message["data"]["slide_id"] == str(slide_id)

    @pytest.mark.asyncio
    async def test_handle_add_slide_message(self, mock_websocket):
        """Test handling add slide message."""
        deck_id = uuid4()
        user_id = "test-user-123"

        message_data = json.dumps(
            {
                "type": "add_slide",
                "data": {"position": 3, "prompt": "Add a slide about market analysis"},
            }
        )

        mock_deck_service = AsyncMock()
        mock_slide_service = AsyncMock()
        mock_connection_manager = AsyncMock()

        with patch("app.api.websocket.connection_manager", mock_connection_manager):
            await _handle_client_message(
                mock_websocket,
                message_data,
                deck_id,
                user_id,
                mock_deck_service,
                mock_slide_service,
            )

        # Assertions
        mock_slide_service.add_slide.assert_called_once_with(
            deck_id, 3, "Add a slide about market analysis", user_id
        )

        mock_connection_manager.send_personal_message.assert_called_once()
        response_message = json.loads(
            mock_connection_manager.send_personal_message.call_args[0][0]
        )
        assert response_message["type"] == "slide_add_queued"
        assert response_message["data"]["position"] == 3

    @pytest.mark.asyncio
    async def test_handle_ping_message(self, mock_websocket):
        """Test handling ping message."""
        deck_id = uuid4()
        user_id = "test-user-123"

        message_data = json.dumps({"type": "ping", "data": {}})

        mock_deck_service = AsyncMock()
        mock_slide_service = AsyncMock()
        mock_connection_manager = AsyncMock()

        with (
            patch("app.api.websocket.connection_manager", mock_connection_manager),
            patch("asyncio.get_event_loop") as mock_loop,
        ):
            mock_loop.return_value.time.return_value = 123456.789

            await _handle_client_message(
                mock_websocket,
                message_data,
                deck_id,
                user_id,
                mock_deck_service,
                mock_slide_service,
            )

        # Assertions
        mock_connection_manager.send_personal_message.assert_called_once()
        response_message = json.loads(
            mock_connection_manager.send_personal_message.call_args[0][0]
        )
        assert response_message["type"] == "pong"
        assert response_message["data"]["timestamp"] == 123456.789

    @pytest.mark.asyncio
    async def test_handle_unknown_message_type(self, mock_websocket):
        """Test handling unknown message type."""
        deck_id = uuid4()
        user_id = "test-user-123"

        message_data = json.dumps({"type": "unknown_type", "data": {}})

        mock_deck_service = AsyncMock()
        mock_slide_service = AsyncMock()
        mock_connection_manager = AsyncMock()

        with patch("app.api.websocket.connection_manager", mock_connection_manager):
            await _handle_client_message(
                mock_websocket,
                message_data,
                deck_id,
                user_id,
                mock_deck_service,
                mock_slide_service,
            )

        # Should send error message
        mock_connection_manager.send_personal_message.assert_called_once()
        error_message = json.loads(
            mock_connection_manager.send_personal_message.call_args[0][0]
        )
        assert error_message["type"] == "error"
        assert "Unknown message type" in error_message["data"]["message"]

    @pytest.mark.asyncio
    async def test_handle_invalid_json_message(self, mock_websocket):
        """Test handling invalid JSON message."""
        deck_id = uuid4()
        user_id = "test-user-123"

        message_data = "invalid json"

        mock_deck_service = AsyncMock()
        mock_slide_service = AsyncMock()
        mock_connection_manager = AsyncMock()

        with patch("app.api.websocket.connection_manager", mock_connection_manager):
            await _handle_client_message(
                mock_websocket,
                message_data,
                deck_id,
                user_id,
                mock_deck_service,
                mock_slide_service,
            )

        # Should send error message
        mock_connection_manager.send_personal_message.assert_called_once()
        error_message = json.loads(
            mock_connection_manager.send_personal_message.call_args[0][0]
        )
        assert error_message["type"] == "error"
        assert "Invalid JSON message" in error_message["data"]["message"]

    @pytest.mark.asyncio
    async def test_handle_slide_update_service_error(self, mock_websocket):
        """Test handling slide update with service error."""
        deck_id = uuid4()
        user_id = "test-user-123"
        slide_id = uuid4()

        message_data = json.dumps(
            {
                "type": "update_slide",
                "data": {"slide_id": str(slide_id), "prompt": "Update prompt"},
            }
        )

        mock_deck_service = AsyncMock()
        mock_slide_service = AsyncMock()
        mock_slide_service.update_slide.side_effect = Exception("Service error")
        mock_connection_manager = AsyncMock()

        with patch("app.api.websocket.connection_manager", mock_connection_manager):
            await _handle_client_message(
                mock_websocket,
                message_data,
                deck_id,
                user_id,
                mock_deck_service,
                mock_slide_service,
            )

        # Should send error message
        mock_connection_manager.send_personal_message.assert_called_once()
        error_message = json.loads(
            mock_connection_manager.send_personal_message.call_args[0][0]
        )
        assert error_message["type"] == "error"
        assert "Failed to update slide" in error_message["data"]["message"]
