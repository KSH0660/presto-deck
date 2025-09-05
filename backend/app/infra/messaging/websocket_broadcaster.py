"""
WebSocket broadcaster for real-time updates.
"""

from typing import Dict, Any, List
import json
import redis.asyncio as redis
from fastapi import WebSocket
from app.infra.config.logging_config import get_logger
from app.application.ports import WebSocketBroadcasterPort


class WebSocketBroadcaster(WebSocketBroadcasterPort):
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self._connections: Dict[str, List[WebSocket]] = {}  # user_id -> [websockets]
        self._deck_connections: Dict[str, List[WebSocket]] = (
            {}
        )  # deck_id -> [websockets]
        self._log = get_logger("infra.websocket")

    async def connect_user(self, user_id: str, websocket: WebSocket):
        """Connect a user's WebSocket."""
        await websocket.accept()

        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(websocket)
        self._log.info("ws.connect.user", user_id=user_id)

    async def connect_deck(self, deck_id: str, websocket: WebSocket):
        """Connect a WebSocket to a specific deck."""
        if deck_id not in self._deck_connections:
            self._deck_connections[deck_id] = []
        self._deck_connections[deck_id].append(websocket)
        self._log.info("ws.connect.deck", deck_id=deck_id)

    async def disconnect_user(self, user_id: str, websocket: WebSocket):
        """Disconnect a user's WebSocket."""
        if user_id in self._connections:
            try:
                self._connections[user_id].remove(websocket)
                if not self._connections[user_id]:
                    del self._connections[user_id]
            except ValueError:
                pass  # WebSocket not in list
        self._log.info("ws.disconnect.user", user_id=user_id)

    async def disconnect_deck(self, deck_id: str, websocket: WebSocket):
        """Disconnect a WebSocket from a deck."""
        if deck_id in self._deck_connections:
            try:
                self._deck_connections[deck_id].remove(websocket)
                if not self._deck_connections[deck_id]:
                    del self._deck_connections[deck_id]
            except ValueError:
                pass
        self._log.info("ws.disconnect.deck", deck_id=deck_id)

    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]):
        """Broadcast message to all user's WebSocket connections."""
        if user_id in self._connections:
            message_str = json.dumps(message)

            # Send to direct connections
            disconnected = []
            for websocket in self._connections[user_id]:
                try:
                    await websocket.send_text(message_str)
                except Exception:
                    disconnected.append(websocket)

            # Remove disconnected WebSockets
            for websocket in disconnected:
                await self.disconnect_user(user_id, websocket)

        # Also publish to Redis Pub/Sub for horizontal scaling
        await self.redis_client.publish(f"user:{user_id}", json.dumps(message))
        self._log.info("ws.broadcast.user", user_id=user_id)

    async def broadcast_to_deck(self, deck_id: str, message: Dict[str, Any]):
        """Broadcast message to all deck's WebSocket connections."""
        if deck_id in self._deck_connections:
            message_str = json.dumps(message)

            # Send to direct connections
            disconnected = []
            for websocket in self._deck_connections[deck_id]:
                try:
                    await websocket.send_text(message_str)
                except Exception:
                    disconnected.append(websocket)

            # Remove disconnected WebSockets
            for websocket in disconnected:
                await self.disconnect_deck(deck_id, websocket)

        # Also publish to Redis Pub/Sub for horizontal scaling
        await self.redis_client.publish(f"deck:{deck_id}", json.dumps(message))
        self._log.info("ws.broadcast.deck", deck_id=deck_id)

    async def get_connected_users(self) -> List[str]:
        """Get list of currently connected user IDs."""
        return list(self._connections.keys())

    async def get_connected_decks(self) -> List[str]:
        """Get list of deck IDs with active connections."""
        return list(self._deck_connections.keys())
