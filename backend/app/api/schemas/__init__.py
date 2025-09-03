"""
API Schemas package with organized, feature-based schema modules.

Import organization:
- base: Common enums, pagination, source types
- deck: Deck creation, status, metadata operations
- slide: Slide CRUD, versioning, batch operations
- websocket: Real-time events, WebSocket management

Usage:
    from app.api.schemas.deck import CreateDeckRequest, DeckStatusResponse
    from app.api.schemas.slide import SlideOut, PatchSlideRequest
    from app.api.schemas.websocket import DeckEventOut
    from app.api.schemas.base import Pagination
"""

from __future__ import annotations

# Re-export commonly used schemas for backward compatibility
from .base import (
    DeckStatus,
    EventType,
    Pagination,
    DeckSource,
    SourceUrl,
    SourceFile,
    SourceText,
    BaseResponse,
    ErrorResponse,
)

from .deck import (
    CreateDeckRequest,
    CreateDeckResponse,
    DeckStatusResponse,
    DeckSummary,
    DeckListResponse,
    DeckDetailsResponse,
    UpdateDeckMetadataRequest,
    CancelDeckRequest,
    CancelDeckResponse,
    RegenerateDeckRequest,
)

from .slide import (
    SlideOut,
    SlideListResponse,
    PatchSlideRequest,
    InsertSlideRequest,
    BulkSlideUpdateRequest,
    ReorderSlidesItem,
    ReorderSlidesRequest,
    DuplicateSlideRequest,
    DeleteSlideResponse,
    RestoreSlideRequest,
    SlideVersionOut,
    SlideVersionListResponse,
    RevertSlideRequest,
    CompareVersionsResponse,
    ChangeSlideTemplateRequest,
    SlideTemplatePreviewResponse,
    ExportSlideRequest,
    ExportSlideResponse,
)

from .websocket import (
    DeckEventOut,
    EventReplayRequest,
    EventReplayResponse,
    WebSocketConnectionRequest,
    WebSocketConnectionResponse,
    WebSocketMessage,
    PingMessage,
    PongMessage,
    ErrorMessage,
    SubscriptionMessage,
    UnsubscribeMessage,
    ConnectionStatsResponse,
    BroadcastMessage,
    BroadcastResponse,
    WebhookEventPayload,
    WebhookRegistration,
    # Event data classes
    DeckStartedEventData,
    SlideAddedEventData,
    SlideEditedEventData,
    SlideDeletedEventData,
    DeckCompletedEventData,
    ErrorEventData,
)

__all__ = [
    # Base types
    "DeckStatus",
    "EventType",
    "Pagination",
    "DeckSource",
    "SourceUrl",
    "SourceFile",
    "SourceText",
    "BaseResponse",
    "ErrorResponse",
    # Deck schemas
    "CreateDeckRequest",
    "CreateDeckResponse",
    "DeckStatusResponse",
    "DeckSummary",
    "DeckListResponse",
    "DeckDetailsResponse",
    "UpdateDeckMetadataRequest",
    "CancelDeckRequest",
    "CancelDeckResponse",
    "RegenerateDeckRequest",
    # Slide schemas
    "SlideOut",
    "SlideListResponse",
    "PatchSlideRequest",
    "InsertSlideRequest",
    "BulkSlideUpdateRequest",
    "ReorderSlidesItem",
    "ReorderSlidesRequest",
    "DuplicateSlideRequest",
    "DeleteSlideResponse",
    "RestoreSlideRequest",
    "SlideVersionOut",
    "SlideVersionListResponse",
    "RevertSlideRequest",
    "CompareVersionsResponse",
    "ChangeSlideTemplateRequest",
    "SlideTemplatePreviewResponse",
    "ExportSlideRequest",
    "ExportSlideResponse",
    # WebSocket schemas
    "DeckEventOut",
    "EventReplayRequest",
    "EventReplayResponse",
    "WebSocketConnectionRequest",
    "WebSocketConnectionResponse",
    "WebSocketMessage",
    "PingMessage",
    "PongMessage",
    "ErrorMessage",
    "SubscriptionMessage",
    "UnsubscribeMessage",
    "ConnectionStatsResponse",
    "BroadcastMessage",
    "BroadcastResponse",
    "WebhookEventPayload",
    "WebhookRegistration",
    "DeckStartedEventData",
    "SlideAddedEventData",
    "SlideEditedEventData",
    "SlideDeletedEventData",
    "DeckCompletedEventData",
    "ErrorEventData",
]
