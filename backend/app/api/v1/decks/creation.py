"""
Deck creation endpoints.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import CreateDeckRequest, CreateDeckResponse
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
from app.infra.config.logging_config import get_logger, bind_context

router = APIRouter()
log = get_logger("api.decks.creation")


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
        bind_context(user_id=str(current_user_id))
        log.info(
            "deck.create.request",
            prompt_len=len(request.prompt),
            has_style=bool(request.style_preferences),
        )
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

        response = CreateDeckResponse(
            deck_id=str(result["deck_id"]),
            status=result["status"],
            message="Deck creation started. Connect to WebSocket for real-time updates.",
        )
        log.info(
            "deck.create.success", deck_id=response.deck_id, status=response.status
        )
        return response

    except ValueError as e:
        # Domain validation errors (prompt too short, invalid style preferences, etc.)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        # Propagate explicit HTTP errors like 401
        raise
    except Exception as e:
        # Log the error in production
        log.exception("deck.create.error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create deck. Please try again.",
        )
