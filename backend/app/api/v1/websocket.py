"""
WebSocket endpoints for real-time deck and slide updates.
"""

from uuid import UUID
from typing import Optional, Dict, Any
from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    Depends,
    HTTPException,
    Query,
)
import json
import asyncio

from app.infra.config.dependencies import (
    get_websocket_broadcaster,
    verify_websocket_token,
)
from app.infra.messaging.websocket_broadcaster import WebSocketBroadcaster
from app.data.queries.deck_queries import DeckQueries

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/decks/{deck_id}")
async def websocket_deck_updates(
    websocket: WebSocket,
    deck_id: UUID,
    token: Optional[str] = Query(None),
    last_version: Optional[int] = Query(0),  # For event replay
):
    """
    WebSocket endpoint for real-time deck updates.

    Supports event replay from a specific version to handle reconnections.

    Query Parameters:
    - token: JWT authentication token
    - last_version: Last event version seen (for replay)

    Message Format:
    {
        "type": "DeckStarted|SlideAdded|SlideUpdated|SlideDeleted|DeckCompleted|Error",
        "deck_id": "uuid",
        "data": {...},
        "version": 123,
        "timestamp": "2023-12-01T10:00:00Z"
    }
    """
    # Authenticate WebSocket connection
    try:
        user_id = await verify_websocket_token(token) if token else None
        if not user_id:
            await websocket.close(code=4001, reason="Authentication required")
            return
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Verify user has access to deck
    try:
        from app.infra.config.database import async_session

        async with async_session() as db_session:
            deck_query = DeckQueries(db_session)
            deck_info = await deck_query.get_deck_status(deck_id, user_id)

            if not deck_info:
                await websocket.close(
                    code=4004, reason="Deck not found or access denied"
                )
                return
    except Exception:
        await websocket.close(code=4000, reason="Database error")
        return

    # Get WebSocket broadcaster
    ws_broadcaster = get_websocket_broadcaster()

    try:
        # Connect to deck updates
        await ws_broadcaster.connect_deck(str(deck_id), websocket)

        # Send replay events if requested
        if last_version > 0:
            # In a full implementation, this would query the deck_events table
            # and send all events with version > last_version
            replay_events = await get_replay_events(deck_id, last_version)
            for event in replay_events:
                await websocket.send_text(json.dumps(event))

        # Send initial connection confirmation
        await websocket.send_text(
            json.dumps(
                {
                    "type": "connected",
                    "deck_id": str(deck_id),
                    "message": "Connected to deck updates",
                    "timestamp": None,  # Would use actual timestamp in production
                }
            )
        )

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # WebSocket connections are primarily for receiving updates
                # But we can handle ping/pong or subscription changes here
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(data)

                if message.get("type") == "ping":
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "pong",
                                "timestamp": None,  # Would use actual timestamp in production
                            }
                        )
                    )
                elif message.get("type") == "subscribe_events":
                    # Handle subscription to specific event types
                    pass

            except asyncio.TimeoutError:
                # Send keepalive ping
                await websocket.send_text(
                    json.dumps({"type": "ping", "timestamp": None})
                )
            except json.JSONDecodeError:
                # Invalid JSON from client
                pass

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error for deck {deck_id}: {e}")
    finally:
        # Clean up connection
        await ws_broadcaster.disconnect_deck(str(deck_id), websocket)


@router.websocket("/user/{user_id}/decks")
async def websocket_user_updates(
    websocket: WebSocket,
    user_id: UUID,
    token: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for user-level updates across all their decks.

    Useful for dashboard/overview pages where users need updates from multiple decks.
    """
    # Authenticate WebSocket connection
    try:
        authenticated_user_id = await verify_websocket_token(token) if token else None
        if not authenticated_user_id or authenticated_user_id != user_id:
            await websocket.close(code=4001, reason="Authentication required")
            return
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Get WebSocket broadcaster
    ws_broadcaster = get_websocket_broadcaster()

    try:
        # Connect to user updates
        await ws_broadcaster.connect_user(str(user_id), websocket)

        # Send initial connection confirmation
        await websocket.send_text(
            json.dumps(
                {
                    "type": "connected",
                    "user_id": str(user_id),
                    "message": "Connected to user updates",
                    "timestamp": None,
                }
            )
        )

        # Keep connection alive
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(data)

                if message.get("type") == "ping":
                    await websocket.send_text(
                        json.dumps({"type": "pong", "timestamp": None})
                    )

            except asyncio.TimeoutError:
                await websocket.send_text(
                    json.dumps({"type": "ping", "timestamp": None})
                )
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error for user {user_id}: {e}")
    finally:
        await ws_broadcaster.disconnect_user(str(user_id), websocket)


async def get_replay_events(deck_id: UUID, since_version: int) -> list[Dict[str, Any]]:
    """
    Get events for replay after reconnection.

    In a full implementation, this would query the deck_events table
    and return all events with version > since_version.
    """
    # Placeholder implementation - would integrate with event sourcing
    return [
        {
            "type": "replay_complete",
            "deck_id": str(deck_id),
            "since_version": since_version,
            "message": f"Replayed events since version {since_version}",
            "timestamp": None,
        }
    ]


# HTTP endpoints for WebSocket management
@router.get("/connections/stats")
async def get_connection_stats(
    ws_broadcaster: WebSocketBroadcaster = Depends(get_websocket_broadcaster),
) -> Dict[str, Any]:
    """
    Get WebSocket connection statistics.

    Useful for monitoring and debugging.
    """
    try:
        connected_users = await ws_broadcaster.get_connected_users()
        connected_decks = await ws_broadcaster.get_connected_decks()

        return {
            "connected_users": len(connected_users),
            "connected_decks": len(connected_decks),
            "users": connected_users,
            "decks": connected_decks,
        }
    except Exception as e:
        print(f"Error getting connection stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get connection stats")


@router.post("/decks/{deck_id}/broadcast")
async def broadcast_to_deck(
    deck_id: UUID,
    message: Dict[str, Any],
    ws_broadcaster: WebSocketBroadcaster = Depends(get_websocket_broadcaster),
) -> Dict[str, str]:
    """
    Manually broadcast a message to all clients connected to a deck.

    For testing and administrative purposes.
    """
    try:
        await ws_broadcaster.broadcast_to_deck(str(deck_id), message)
        return {
            "status": "success",
            "message": f"Broadcasted to deck {deck_id}",
        }
    except Exception as e:
        print(f"Error broadcasting to deck {deck_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to broadcast message")


@router.post("/users/{user_id}/broadcast")
async def broadcast_to_user(
    user_id: UUID,
    message: Dict[str, Any],
    ws_broadcaster: WebSocketBroadcaster = Depends(get_websocket_broadcaster),
) -> Dict[str, str]:
    """
    Manually broadcast a message to all clients connected to a user.

    For testing and administrative purposes.
    """
    try:
        await ws_broadcaster.broadcast_to_user(str(user_id), message)
        return {
            "status": "success",
            "message": f"Broadcasted to user {user_id}",
        }
    except Exception as e:
        print(f"Error broadcasting to user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to broadcast message")
