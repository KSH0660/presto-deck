"""
API dependencies for dependency injection.

This module provides FastAPI dependency functions for common concerns
like authentication, authorization, database sessions, and service injection.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.infra.config.dependencies import (
    get_database_session,
    get_deck_repository,
    get_slide_repository,
    get_event_repository,
    get_arq_client,
    get_websocket_broadcaster,
    get_llm_client,
    get_template_service,
)
from app.infra.auth.jwt_auth import JWTAuth
from app.application.unit_of_work import UnitOfWork
from app.application.use_cases.create_deck_plan import CreateDeckPlanUseCase
from app.application.use_cases.complete_deck import CompleteDeckUseCase
from app.application.use_cases.reorder_slides import ReorderSlidesUseCase
from app.application.services.template_selector import TemplateSelectionService
from app.application.services.deck_pipeline import DeckPipelineService


# Security
security = HTTPBearer()
jwt_auth = JWTAuth()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UUID:
    """
    Get the current authenticated user from JWT token.

    Args:
        credentials: JWT token credentials

    Returns:
        UUID: The authenticated user's ID

    Raises:
        HTTPException: If token is invalid or user not found
    """
    try:
        payload = jwt_auth.verify_token(credentials.credentials)
        user_id = payload.get("user_id")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
            )

        return UUID(user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {str(e)}"
        )


async def get_unit_of_work(
    session: AsyncSession = Depends(get_database_session),
) -> UnitOfWork:
    """
    Create a Unit of Work instance with repositories.

    Args:
        session: Database session

    Returns:
        UnitOfWork: Configured unit of work instance
    """
    deck_repo = await get_deck_repository(session)
    slide_repo = await get_slide_repository(session)
    event_repo = await get_event_repository(session)

    return UnitOfWork(
        session=session,
        deck_repo=deck_repo,
        slide_repo=slide_repo,
        event_repo=event_repo,
    )


async def get_template_selection_service(
    template_service=Depends(get_template_service),
) -> TemplateSelectionService:
    """
    Create a Template Selection Service instance.

    Args:
        template_service: Template service dependency

    Returns:
        TemplateSelectionService: Configured service instance
    """
    return TemplateSelectionService(template_service)


async def get_deck_pipeline_service(
    llm_client=Depends(get_llm_client),
    template_service=Depends(get_template_service),
    arq_client=Depends(get_arq_client),
    ws_broadcaster=Depends(get_websocket_broadcaster),
) -> DeckPipelineService:
    """
    Create a Deck Pipeline Service instance.

    Args:
        llm_client: LLM service dependency
        template_service: Template service dependency
        arq_client: Message broker dependency
        ws_broadcaster: WebSocket broadcaster dependency

    Returns:
        DeckPipelineService: Configured service instance
    """
    return DeckPipelineService(
        llm_service=llm_client,
        template_service=template_service,
        message_broker=arq_client,
        ws_broadcaster=ws_broadcaster,
    )


# Use Case Dependencies
async def get_create_deck_use_case(
    uow: UnitOfWork = Depends(get_unit_of_work),
    arq_client=Depends(get_arq_client),
    ws_broadcaster=Depends(get_websocket_broadcaster),
    template_selector: TemplateSelectionService = Depends(
        get_template_selection_service
    ),
) -> CreateDeckPlanUseCase:
    """
    Create a CreateDeckPlanUseCase instance.

    Args:
        uow: Unit of Work dependency
        arq_client: Message broker dependency
        ws_broadcaster: WebSocket broadcaster dependency
        template_selector: Template selection service dependency

    Returns:
        CreateDeckPlanUseCase: Configured use case instance
    """
    return CreateDeckPlanUseCase(
        uow=uow,
        message_broker=arq_client,
        ws_broadcaster=ws_broadcaster,
        template_selector=template_selector,
    )


async def get_complete_deck_use_case(
    uow: UnitOfWork = Depends(get_unit_of_work),
    ws_broadcaster=Depends(get_websocket_broadcaster),
) -> CompleteDeckUseCase:
    """
    Create a CompleteDeckUseCase instance.

    Args:
        uow: Unit of Work dependency
        ws_broadcaster: WebSocket broadcaster dependency

    Returns:
        CompleteDeckUseCase: Configured use case instance
    """
    return CompleteDeckUseCase(uow=uow, ws_broadcaster=ws_broadcaster)


async def get_reorder_slides_use_case(
    uow: UnitOfWork = Depends(get_unit_of_work),
    ws_broadcaster=Depends(get_websocket_broadcaster),
) -> ReorderSlidesUseCase:
    """
    Create a ReorderSlidesUseCase instance.

    Args:
        uow: Unit of Work dependency
        ws_broadcaster: WebSocket broadcaster dependency

    Returns:
        ReorderSlidesUseCase: Configured use case instance
    """
    return ReorderSlidesUseCase(uow=uow, ws_broadcaster=ws_broadcaster)


async def verify_deck_ownership(
    deck_id: UUID,
    current_user: UUID = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> UUID:
    """
    Verify that the current user owns the specified deck.

    Args:
        deck_id: ID of the deck to verify
        current_user: Current authenticated user
        uow: Unit of Work for database access

    Returns:
        UUID: The deck ID if ownership is verified

    Raises:
        HTTPException: If deck not found or user doesn't own it
    """
    async with uow:
        deck = await uow.deck_repo.get_by_id(deck_id)

        if not deck:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Deck {deck_id} not found",
            )

        if deck.user_id != current_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this deck",
            )

    return deck_id
