"""
FastAPI router for deck operations.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.deck_schemas import (
    CreateDeckRequest,
    CreateDeckResponse,
    DeckStatusResponse,
)
from app.application.use_cases.create_plan_and_render import CreatePlanAndRenderUseCase
from app.application.unit_of_work import UnitOfWork
from app.data.repositories.deck_repository import DeckRepository
from app.data.repositories.event_repository import EventRepository
from app.infra.messaging.arq_client import ARQClient
from app.infra.messaging.websocket_broadcaster import WebSocketBroadcaster
from app.infra.config.database import get_db_session
from app.infra.config.dependencies import (
    get_current_user_id,
    get_arq_client,
    get_websocket_broadcaster,
)


router = APIRouter(prefix="/decks", tags=["decks"])


@router.post("/", response_model=CreateDeckResponse)
async def create_deck(
    request: CreateDeckRequest,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
    arq_client: ARQClient = Depends(get_arq_client),
    ws_broadcaster: WebSocketBroadcaster = Depends(get_websocket_broadcaster),
) -> CreateDeckResponse:
    """
    Create a new presentation deck.

    This endpoint initiates the deck creation process:
    1. Validates the request
    2. Creates deck record in database
    3. Enqueues background job for LLM processing
    4. Returns deck_id for tracking
    """
    try:
        # Dependency injection - assemble use case
        uow = UnitOfWork(db_session)
        deck_repo = DeckRepository(db_session)
        event_repo = EventRepository(db_session)

        use_case = CreatePlanAndRenderUseCase(
            uow=uow,
            deck_repo=deck_repo,
            event_repo=event_repo,
            arq_client=arq_client,
            ws_broadcaster=ws_broadcaster,
        )

        # Execute use case
        result = await use_case.execute(
            user_id=current_user_id,
            prompt=request.prompt,
            style_preferences=request.style_preferences,
        )

        return CreateDeckResponse(**result)

    except ValueError as e:
        # Domain validation errors
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        # Unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create deck",
        )


@router.get("/{deck_id}/status", response_model=DeckStatusResponse)
async def get_deck_status(
    deck_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
) -> DeckStatusResponse:
    """Get current status of a deck (read operation - no use case needed)."""
    # For simple queries, bypass use cases and go directly to query layer
    from app.data.queries.deck_queries import DeckQueries

    deck_query = DeckQueries(db_session)
    deck_info = await deck_query.get_deck_status(deck_id, current_user_id)

    if not deck_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found"
        )

    return DeckStatusResponse(**deck_info)
