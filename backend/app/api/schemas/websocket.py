"""
WebSocket and real-time event schemas.
Handles WebSocket connection management, event streaming, and real-time updates.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base import EventType, BaseResponse


# ---------- WEBSOCKET CONNECTION SCHEMAS ----------
class WebSocketConnectionRequest(BaseModel):
    """WebSocket connection initialization parameters."""

    last_version: Optional[int] = Field(
        0, ge=0, description="Last event version seen (for replay on reconnect)"
    )
    event_types: Optional[List[EventType]] = Field(
        None, description="Filter to only receive specific event types"
    )
    include_history: bool = Field(
        False, description="Include historical events in initial response"
    )


class WebSocketConnectionResponse(BaseModel):
    """Initial response sent on WebSocket connection."""

    type: str = "connected"
    deck_id: Optional[str] = None
    user_id: Optional[str] = None
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    server_version: Optional[str] = None


# ---------- EVENT STREAMING SCHEMAS ----------
class DeckEventOut(BaseModel):
    """
    Standard event format for WebSocket streaming.

    Used for all real-time updates including deck status changes,
    slide modifications, and system events.
    """

    id: str = Field(..., description="Unique event ID")
    deck_id: str = Field(..., description="Associated deck ID")
    event_type: EventType = Field(..., description="Type of event")
    event_data: Dict[str, Any] = Field(..., description="Event-specific payload")
    version: Optional[int] = Field(None, description="Event sequence number")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # User context
    created_by: Optional[str] = Field(None, description="User ID who triggered event")
    session_id: Optional[str] = Field(None, description="Session that created event")

    # Event metadata
    correlation_id: Optional[str] = Field(
        None, description="Correlation ID for tracking related events"
    )
    parent_event_id: Optional[str] = Field(
        None, description="Parent event ID for event chains"
    )


class EventReplayRequest(BaseModel):
    """Request to replay events from a specific point."""

    since_version: int = Field(..., ge=0)
    event_types: Optional[List[EventType]] = None
    limit: int = Field(100, ge=1, le=1000)


class EventReplayResponse(BaseModel):
    """Response containing replayed events."""

    events: List[DeckEventOut]
    has_more: bool = Field(..., description="Whether more events are available")
    next_version: Optional[int] = Field(None, description="Next version to request")


# ---------- WEBSOCKET MESSAGE TYPES ----------
class WebSocketMessage(BaseModel):
    """Base WebSocket message format."""

    type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PingMessage(WebSocketMessage):
    """Keepalive ping message."""

    type: str = "ping"


class PongMessage(WebSocketMessage):
    """Keepalive pong response."""

    type: str = "pong"


class ErrorMessage(WebSocketMessage):
    """Error message over WebSocket."""

    type: str = "error"
    error_code: str
    error_message: str
    retry_after: Optional[int] = Field(None, description="Seconds to wait before retry")


class SubscriptionMessage(WebSocketMessage):
    """Message to change event subscriptions."""

    type: str = "subscribe"
    event_types: List[EventType]
    deck_ids: Optional[List[str]] = Field(
        None, description="Limit to specific decks (default: all user's decks)"
    )


class UnsubscribeMessage(WebSocketMessage):
    """Message to remove event subscriptions."""

    type: str = "unsubscribe"
    event_types: Optional[List[EventType]] = Field(
        None, description="Event types to unsubscribe from (default: all)"
    )


# ---------- SPECIFIC EVENT PAYLOADS ----------
class DeckStartedEventData(BaseModel):
    """Payload for DeckStarted events."""

    deck_id: str
    user_id: str
    prompt: str
    estimated_slides: Optional[int] = None
    template_type: Optional[str] = None


class SlideAddedEventData(BaseModel):
    """Payload for SlideAdded events."""

    slide_id: str
    deck_id: str
    order: int
    title: str
    template_type: str
    generation_method: str = Field(description="ai|user|template")


class SlideEditedEventData(BaseModel):
    """Payload for SlideEdited events."""

    slide_id: str
    deck_id: str
    changes: Dict[str, Any] = Field(description="Fields that were changed")
    version_no: int
    edit_type: str = Field(description="user_edit|ai_edit|template_change")


class SlideDeletedEventData(BaseModel):
    """Payload for SlideDeleted events."""

    slide_id: str
    deck_id: str
    former_order: int
    soft_deleted: bool = True


class DeckCompletedEventData(BaseModel):
    """Payload for DeckCompleted events."""

    deck_id: str
    final_slide_count: int
    total_generation_time: Optional[float] = Field(
        None, description="Total generation time in seconds"
    )
    template_type: str


class ErrorEventData(BaseModel):
    """Payload for Error events."""

    error_type: str
    error_message: str
    deck_id: Optional[str] = None
    slide_id: Optional[str] = None
    recoverable: bool = Field(True, description="Whether the error is recoverable")
    retry_suggested: bool = Field(False, description="Whether retry is suggested")


# ---------- WEBSOCKET MANAGEMENT SCHEMAS ----------
class ConnectionStatsResponse(BaseModel):
    """WebSocket connection statistics."""

    connected_users: int
    connected_decks: int
    total_connections: int
    active_streams: int

    # Detailed breakdowns
    users: Optional[List[str]] = None
    decks: Optional[List[str]] = None
    connection_uptime: Optional[float] = Field(
        None, description="Average connection uptime in seconds"
    )


class BroadcastMessage(BaseModel):
    """Manual message broadcasting for testing/admin."""

    message: Dict[str, Any]
    target_type: str = Field(description="user|deck|all")
    target_ids: Optional[List[str]] = Field(
        None, description="Specific user/deck IDs (if not broadcasting to all)"
    )


class BroadcastResponse(BaseResponse):
    """Response to broadcast request."""

    targets_reached: int
    broadcast_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------- WEBHOOK INTEGRATION ----------
class WebhookEventPayload(BaseModel):
    """
    Event payload for webhook notifications.

    Alternative to WebSocket for systems that prefer HTTP callbacks.
    """

    webhook_id: str
    event: DeckEventOut
    attempt: int = Field(1, ge=1, description="Delivery attempt number")
    signature: str = Field(..., description="HMAC signature for verification")


class WebhookRegistration(BaseModel):
    """Register webhook endpoint for event notifications."""

    url: str = Field(..., description="Webhook endpoint URL")
    event_types: List[EventType] = Field(..., description="Events to receive")
    secret: str = Field(..., description="Shared secret for signature verification")
    active: bool = Field(True, description="Whether webhook is active")

    # Filtering options
    deck_filter: Optional[List[str]] = Field(
        None, description="Only events from these decks"
    )
    user_filter: Optional[List[str]] = Field(
        None, description="Only events from these users"
    )
