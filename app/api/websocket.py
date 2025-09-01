import asyncio
import json
from typing import Dict, Optional, Set
from uuid import UUID

import structlog
from fastapi import WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from starlette.websockets import WebSocketState

from app.api.schemas import WebSocketMessage, SlideUpdateRequest, SlideAddRequest
from app.application.services import DeckService, SlideService
from app.core.dependencies import get_deck_service, get_slide_service
from app.core.observability import metrics
from app.core.security import security_service
from app.domain.exceptions import UnauthorizedAccessException, DeckNotFoundException
from app.infrastructure.messaging.redis_client import RedisPubSubManager

logger = structlog.get_logger(__name__)

# Global connection manager
connection_manager: Optional["WebSocketManager"] = None


class WebSocketManager:
    """Manages WebSocket connections and message broadcasting."""
    
    def __init__(self, redis_pubsub: RedisPubSubManager) -> None:
        self.active_connections: Dict[UUID, Set[WebSocket]] = {}
        self.redis_pubsub = redis_pubsub
        self._consumers: Dict[UUID, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket, deck_id: UUID, user_id: str) -> None:
        """Accept WebSocket connection and start listening for events."""
        await websocket.accept()
        
        if deck_id not in self.active_connections:
            self.active_connections[deck_id] = set()
            # Start Redis consumer for this deck
            self._consumers[deck_id] = asyncio.create_task(
                self._consume_deck_events(deck_id)
            )
        
        self.active_connections[deck_id].add(websocket)
        metrics.record_websocket_connection(1)
        
        logger.info(
            "WebSocket connected",
            deck_id=str(deck_id),
            user_id=user_id,
            connections=len(self.active_connections[deck_id])
        )

    async def disconnect(self, websocket: WebSocket, deck_id: UUID) -> None:
        """Handle WebSocket disconnection."""
        if deck_id in self.active_connections:
            self.active_connections[deck_id].discard(websocket)
            
            # If no more connections for this deck, stop consumer
            if not self.active_connections[deck_id]:
                if deck_id in self._consumers:
                    self._consumers[deck_id].cancel()
                    del self._consumers[deck_id]
                del self.active_connections[deck_id]
        
        metrics.record_websocket_connection(-1)
        logger.info("WebSocket disconnected", deck_id=str(deck_id))

    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        """Send message to specific WebSocket connection."""
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(message)

    async def broadcast_to_deck(self, deck_id: UUID, message: str) -> None:
        """Broadcast message to all connections for a deck."""
        if deck_id in self.active_connections:
            connections_to_remove = set()
            
            for websocket in self.active_connections[deck_id].copy():
                try:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_text(message)
                    else:
                        connections_to_remove.add(websocket)
                except Exception as e:
                    logger.warning("Failed to send message to WebSocket", error=str(e))
                    connections_to_remove.add(websocket)
            
            # Clean up disconnected connections
            for websocket in connections_to_remove:
                await self.disconnect(websocket, deck_id)

    async def _consume_deck_events(self, deck_id: UUID) -> None:
        """Consume Redis events for a specific deck and broadcast to WebSocket clients."""
        try:
            stream = self.redis_pubsub.subscribe_to_deck_channel(deck_id)
            if asyncio.iscoroutine(stream):
                stream = await stream
            async for event in stream:
                message = {
                    "type": "event",
                    "data": {
                        "event_type": event.event_type,
                        "deck_id": str(event.deck_id),
                        "version": event.version,
                        "timestamp": event.timestamp.isoformat(),
                        "payload": event.payload,
                    }
                }
                
                await self.broadcast_to_deck(deck_id, json.dumps(message))
                
                logger.debug(
                    "Event broadcasted to WebSocket clients",
                    deck_id=str(deck_id),
                    event_type=event.event_type,
                    connections=len(self.active_connections.get(deck_id, []))
                )
                
        except asyncio.CancelledError:
            logger.info("Event consumer cancelled for deck", deck_id=str(deck_id))
        except Exception as e:
            logger.error("Event consumer error", deck_id=str(deck_id), error=str(e))


async def websocket_endpoint(
    websocket: WebSocket,
    deck_id: UUID,
    token: str = Query(...),
    last_version: int = Query(default=0),
    deck_service: DeckService = Depends(get_deck_service),
    slide_service: SlideService = Depends(get_slide_service),
):
    """WebSocket endpoint for real-time deck updates."""
    try:
        # Authenticate user
        user_id = security_service.extract_user_id_from_token(token)
        
        # Check deck ownership
        try:
            deck = await deck_service.get_deck(deck_id, user_id)
        except (DeckNotFoundException, UnauthorizedAccessException) as e:
            await websocket.close(code=4003, reason=str(e))
            return
        
        # Connect to WebSocket manager
        if not connection_manager:
            await websocket.close(code=4000, reason="WebSocket service not available")
            return
            
        await connection_manager.connect(websocket, deck_id, user_id)
        
        try:
            # Send event replay if requested
            if last_version > 0:
                await _send_event_replay(websocket, deck_service, deck_id, user_id, last_version)
            
            # Listen for client messages
            while True:
                data = await websocket.receive_text()
                await _handle_client_message(
                    websocket, data, deck_id, user_id, deck_service, slide_service
                )
                
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected by client", deck_id=str(deck_id), user_id=user_id)
        finally:
            await connection_manager.disconnect(websocket, deck_id)
            
    except Exception as e:
        logger.error("WebSocket error", deck_id=str(deck_id), error=str(e))
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=4000, reason="Internal server error")


async def _send_event_replay(
    websocket: WebSocket,
    deck_service: DeckService,
    deck_id: UUID,
    user_id: str,
    from_version: int
) -> None:
    """Send historical events to client for replay."""
    try:
        events = await deck_service.get_deck_events(deck_id, user_id, from_version)
        
        for event in events:
            replay_message = {
                "type": "replay",
                "data": {
                    "event_type": event.event_type,
                    "deck_id": str(event.deck_id),
                    "version": event.version,
                    "timestamp": event.created_at.isoformat(),
                    "payload": event.payload,
                }
            }
            
            await connection_manager.send_personal_message(
                json.dumps(replay_message), websocket
            )
        
        # Send replay complete signal
        complete_message = {
            "type": "replay_complete",
            "data": {"replayed_events": len(events)}
        }
        await connection_manager.send_personal_message(
            json.dumps(complete_message), websocket
        )
        
        logger.info(
            "Event replay completed",
            deck_id=str(deck_id),
            user_id=user_id,
            events_count=len(events)
        )
        
    except Exception as e:
        logger.error("Event replay failed", deck_id=str(deck_id), error=str(e))
        error_message = {
            "type": "error",
            "data": {"message": "Failed to replay events"}
        }
        await connection_manager.send_personal_message(
            json.dumps(error_message), websocket
        )


async def _handle_client_message(
    websocket: WebSocket,
    message_data: str,
    deck_id: UUID,
    user_id: str,
    deck_service: DeckService,
    slide_service: SlideService,
) -> None:
    """Handle incoming WebSocket messages from clients."""
    try:
        message = json.loads(message_data)
        message_type = message.get("type")
        data = message.get("data", {})
        
        if message_type == "update_slide":
            await _handle_slide_update(
                websocket, data, user_id, slide_service
            )
        elif message_type == "add_slide":
            await _handle_slide_addition(
                websocket, data, deck_id, user_id, slide_service
            )
        elif message_type == "ping":
            await _handle_ping(websocket)
        else:
            await _send_error(websocket, f"Unknown message type: {message_type}")
            
    except json.JSONDecodeError:
        await _send_error(websocket, "Invalid JSON message")
    except Exception as e:
        logger.error("Error handling client message", error=str(e))
        await _send_error(websocket, "Internal server error")


async def _handle_slide_update(
    websocket: WebSocket,
    data: Dict,
    user_id: str,
    slide_service: SlideService,
) -> None:
    """Handle slide update request."""
    try:
        request = SlideUpdateRequest(**data)
        await slide_service.update_slide(request.slide_id, request.prompt, user_id)
        
        response = {
            "type": "slide_update_queued",
            "data": {"slide_id": str(request.slide_id)}
        }
        await connection_manager.send_personal_message(json.dumps(response), websocket)
        
    except Exception as e:
        await _send_error(websocket, f"Failed to update slide: {str(e)}")


async def _handle_slide_addition(
    websocket: WebSocket,
    data: Dict,
    deck_id: UUID,
    user_id: str,
    slide_service: SlideService,
) -> None:
    """Handle slide addition request."""
    try:
        request = SlideAddRequest(**data)
        await slide_service.add_slide(deck_id, request.position, request.prompt, user_id)
        
        response = {
            "type": "slide_add_queued",
            "data": {"position": request.position}
        }
        await connection_manager.send_personal_message(json.dumps(response), websocket)
        
    except Exception as e:
        await _send_error(websocket, f"Failed to add slide: {str(e)}")


async def _handle_ping(websocket: WebSocket) -> None:
    """Handle ping message."""
    pong_message = {
        "type": "pong",
        "data": {"timestamp": asyncio.get_event_loop().time()}
    }
    await connection_manager.send_personal_message(json.dumps(pong_message), websocket)


async def _send_error(websocket: WebSocket, error_message: str) -> None:
    """Send error message to WebSocket client."""
    error_response = {
        "type": "error",
        "data": {"message": error_message}
    }
    await connection_manager.send_personal_message(json.dumps(error_response), websocket)
