"""
FastAPI router for deck operations using Use Case-Driven Architecture.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.deck_schemas import (
    CreateDeckRequest,
    CreateDeckResponse,
    DeckStatusResponse,
)
from app.application.use_cases.create_deck_plan import CreateDeckPlanUseCase
from app.application.unit_of_work import UnitOfWork
from app.data.repositories.deck_repository import DeckRepository
from app.data.repositories.event_repository import EventRepository
from app.infra.messaging.arq_client import ARQClient
from app.infra.messaging.websocket_broadcaster import WebSocketBroadcaster
from app.infra.llm.langchain_client import LangChainClient
from app.infra.config.database import get_db_session
from app.infra.config.dependencies import (
    get_current_user_id,
    get_arq_client,
    get_websocket_broadcaster,
    get_llm_client,
)


router = APIRouter(prefix="/decks", tags=["decks"])


@router.post("/", response_model=CreateDeckResponse)
async def create_deck(
    request: CreateDeckRequest,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
    arq_client: ARQClient = Depends(get_arq_client),
    ws_broadcaster: WebSocketBroadcaster = Depends(get_websocket_broadcaster),
    llm_client: LangChainClient = Depends(get_llm_client),
) -> CreateDeckResponse:
    """
    Create a new presentation deck and initiate the planning process.

    This endpoint:
    1. Validates the request using domain rules
    2. Creates deck entity in PENDING status
    3. Generates initial deck plan using LLM
    4. Enqueues template selection job
    5. Returns deck_id for tracking via WebSocket
    """
    try:
        # Assemble dependencies for CreateDeckPlanUseCase
        uow = UnitOfWork(db_session)
        deck_repo = DeckRepository(db_session)
        event_repo = EventRepository(db_session)

        # Create the use case with all required dependencies
        use_case = CreateDeckPlanUseCase(
            uow=uow,
            deck_repo=deck_repo,
            event_repo=event_repo,
            arq_client=arq_client,
            ws_broadcaster=ws_broadcaster,
            llm_client=llm_client,
        )

        # Execute the use case
        result = await use_case.execute(
            user_id=current_user_id,
            prompt=request.prompt,
            style_preferences=request.style_preferences,
        )

        return CreateDeckResponse(
            deck_id=result["deck_id"],
            status=result["status"],
            message="Deck creation started. Connect to WebSocket for real-time updates.",
        )

    except ValueError as e:
        # Domain validation errors (prompt too short, invalid style preferences, etc.)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Log the error in production
        print(f"Unexpected error creating deck: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create deck. Please try again.",
        )


@router.get("/{deck_id}/status", response_model=DeckStatusResponse)
async def get_deck_status(
    deck_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
) -> DeckStatusResponse:
    """
    Get current status of a deck.

    This is a read-only operation that bypasses use cases and goes directly
    to the query layer following CQRS-lite pattern.
    """
    try:
        # Use query layer for read operations (CQRS-lite)
        from app.data.queries.deck_queries import DeckQueries

        deck_query = DeckQueries(db_session)
        deck_info = await deck_query.get_deck_with_slides(deck_id, current_user_id)

        if not deck_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deck not found or access denied",
            )

        return DeckStatusResponse(
            deck_id=str(deck_info["deck_id"]),
            status=deck_info["status"],
            slide_count=deck_info["slide_count"],
            created_at=deck_info["created_at"],
            updated_at=deck_info.get("updated_at"),
            completed_at=deck_info.get("completed_at"),
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        print(f"Error fetching deck status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch deck status",
        )


@router.get("/{deck_id}", response_model=dict)
async def get_deck_details(
    deck_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Get complete deck details including all slides.

    Returns the full deck structure with generated slides for completed decks.
    """
    try:
        from app.data.queries.deck_queries import DeckQueries

        deck_query = DeckQueries(db_session)
        deck_details = await deck_query.get_deck_with_slides(deck_id, current_user_id)

        if not deck_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deck not found or access denied",
            )

        return deck_details

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching deck details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch deck details",
        )


@router.post("/{deck_id}/cancel")
async def cancel_deck(
    deck_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Cancel an in-progress deck generation.

    This sets a cancellation flag in Redis that workers check between operations.
    """
    try:
        # For cancellation, we could create a CancelDeckUseCase, but for now
        # we'll implement it directly as it's a simple operation
        from app.data.queries.deck_queries import DeckQueries
        from app.infra.messaging.redis_client import get_redis_client

        # Verify deck exists and belongs to user
        deck_query = DeckQueries(db_session)
        deck_info = await deck_query.get_deck_status(deck_id, current_user_id)

        if not deck_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deck not found or access denied",
            )

        # Check if deck can be cancelled
        if deck_info["status"] in ["COMPLETED", "FAILED", "CANCELLED"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel deck in {deck_info['status']} status",
            )

        # Set cancellation flag in Redis
        redis_client = get_redis_client()
        await redis_client.setex(f"cancel_deck:{deck_id}", 3600, "true")  # 1 hour TTL

        return {
            "message": "Cancellation request received. Processing will stop at the next checkpoint.",
            "deck_id": str(deck_id),
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error cancelling deck: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel deck",
        )
