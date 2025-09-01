from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.schemas import (
    DeckCreationRequest,
    DeckCreationResponse,
    DeckResponse,
    DeckListResponse,
    CancellationResponse,
    SlideResponse,
)
from app.application.services import DeckService
from app.core.dependencies import (
    get_deck_service,
    get_current_user_id,
)
from app.core.observability import metrics, trace_async_operation
from app.domain.exceptions import (
    DeckNotFoundException,
    UnauthorizedAccessException,
    InvalidDeckStatusException,
)

router = APIRouter(prefix="/decks", tags=["decks"])


@router.post("/", response_model=DeckCreationResponse, status_code=202)
async def create_deck(
    request: DeckCreationRequest,
    user_id: str = Depends(get_current_user_id),
    deck_service: DeckService = Depends(get_deck_service),
) -> DeckCreationResponse:
    """Create a new presentation deck."""
    async with trace_async_operation("api_create_deck", user_id=user_id):
        try:
            deck = await deck_service.create_deck(request, user_id)

            metrics.record_http_request("POST", "/api/v1/decks", 202, 0.0)

            return DeckCreationResponse(
                deck_id=deck.id,
                status=deck.status,
                message="Deck creation started successfully",
            )

        except Exception as e:
            metrics.record_http_request("POST", "/api/v1/decks", 500, 0.0)
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/{deck_id}", response_model=DeckResponse)
async def get_deck(
    deck_id: UUID,
    user_id: str = Depends(get_current_user_id),
    deck_service: DeckService = Depends(get_deck_service),
) -> DeckResponse:
    """Get deck details with all slides."""
    async with trace_async_operation(
        "api_get_deck", deck_id=str(deck_id), user_id=user_id
    ):
        try:
            deck, slides = await deck_service.get_deck_with_slides(deck_id, user_id)

            slide_responses = [
                SlideResponse(
                    id=slide.id,
                    deck_id=slide.deck_id,
                    slide_order=slide.slide_order,
                    html_content=slide.html_content,
                    presenter_notes=slide.presenter_notes,
                    created_at=slide.created_at,
                    updated_at=slide.updated_at,
                )
                for slide in slides
            ]

            metrics.record_http_request("GET", f"/api/v1/decks/{deck_id}", 200, 0.0)

            return DeckResponse(
                id=deck.id,
                user_id=deck.user_id,
                title=deck.title,
                status=deck.status,
                version=deck.version,
                deck_plan=deck.deck_plan,
                slides=slide_responses,
                created_at=deck.created_at,
                updated_at=deck.updated_at,
            )

        except DeckNotFoundException:
            metrics.record_http_request("GET", f"/api/v1/decks/{deck_id}", 404, 0.0)
            raise HTTPException(status_code=404, detail=f"Deck {deck_id} not found")
        except UnauthorizedAccessException:
            metrics.record_http_request("GET", f"/api/v1/decks/{deck_id}", 403, 0.0)
            raise HTTPException(status_code=403, detail="Access denied")
        except Exception as e:
            metrics.record_http_request("GET", f"/api/v1/decks/{deck_id}", 500, 0.0)
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[DeckListResponse])
async def list_decks(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user_id: str = Depends(get_current_user_id),
    deck_service: DeckService = Depends(get_deck_service),
) -> List[DeckListResponse]:
    """List user's decks with pagination."""
    async with trace_async_operation("api_list_decks", user_id=user_id):
        try:
            decks = await deck_service.list_decks(user_id, limit, offset)

            # Get slide counts for each deck (could be optimized with a single query)
            deck_responses = []
            for deck in decks:
                _, slides = await deck_service.get_deck_with_slides(deck.id, user_id)
                deck_responses.append(
                    DeckListResponse(
                        id=deck.id,
                        title=deck.title,
                        status=deck.status,
                        slide_count=len(slides),
                        created_at=deck.created_at,
                        updated_at=deck.updated_at,
                    )
                )

            metrics.record_http_request("GET", "/api/v1/decks", 200, 0.0)
            return deck_responses

        except Exception as e:
            metrics.record_http_request("GET", "/api/v1/decks", 500, 0.0)
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/{deck_id}/cancel", response_model=CancellationResponse, status_code=202)
async def cancel_deck_generation(
    deck_id: UUID,
    user_id: str = Depends(get_current_user_id),
    deck_service: DeckService = Depends(get_deck_service),
) -> CancellationResponse:
    """Cancel ongoing deck generation."""
    async with trace_async_operation(
        "api_cancel_deck", deck_id=str(deck_id), user_id=user_id
    ):
        try:
            deck = await deck_service.cancel_deck_generation(deck_id, user_id)

            metrics.record_http_request(
                "POST", f"/api/v1/decks/{deck_id}/cancel", 202, 0.0
            )

            return CancellationResponse(
                message="Deck generation cancellation requested",
                deck_id=deck_id,
                status=deck.status,
            )

        except DeckNotFoundException:
            metrics.record_http_request(
                "POST", f"/api/v1/decks/{deck_id}/cancel", 404, 0.0
            )
            raise HTTPException(status_code=404, detail=f"Deck {deck_id} not found")
        except UnauthorizedAccessException:
            metrics.record_http_request(
                "POST", f"/api/v1/decks/{deck_id}/cancel", 403, 0.0
            )
            raise HTTPException(status_code=403, detail="Access denied")
        except InvalidDeckStatusException as e:
            metrics.record_http_request(
                "POST", f"/api/v1/decks/{deck_id}/cancel", 400, 0.0
            )
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            metrics.record_http_request(
                "POST", f"/api/v1/decks/{deck_id}/cancel", 500, 0.0
            )
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/{deck_id}/events")
async def get_deck_events(
    deck_id: UUID,
    from_version: int = Query(default=0, ge=0),
    user_id: str = Depends(get_current_user_id),
    deck_service: DeckService = Depends(get_deck_service),
):
    """Get deck events for replay (used by WebSocket clients)."""
    async with trace_async_operation(
        "api_get_deck_events", deck_id=str(deck_id), user_id=user_id
    ):
        try:
            events = await deck_service.get_deck_events(deck_id, user_id, from_version)

            event_responses = [
                {
                    "event_type": event.event_type,
                    "deck_id": str(event.deck_id),
                    "version": event.version,
                    "timestamp": event.created_at.isoformat(),
                    "payload": event.payload,
                }
                for event in events
            ]

            metrics.record_http_request(
                "GET", f"/api/v1/decks/{deck_id}/events", 200, 0.0
            )
            return {"events": event_responses}

        except DeckNotFoundException:
            metrics.record_http_request(
                "GET", f"/api/v1/decks/{deck_id}/events", 404, 0.0
            )
            raise HTTPException(status_code=404, detail=f"Deck {deck_id} not found")
        except UnauthorizedAccessException:
            metrics.record_http_request(
                "GET", f"/api/v1/decks/{deck_id}/events", 403, 0.0
            )
            raise HTTPException(status_code=403, detail="Access denied")
        except Exception as e:
            metrics.record_http_request(
                "GET", f"/api/v1/decks/{deck_id}/events", 500, 0.0
            )
            raise HTTPException(status_code=500, detail=str(e))
