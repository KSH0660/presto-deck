"""
Deck status and details endpoints.
"""

import inspect
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import DeckStatusResponse
from app.data.queries.deck_queries import DeckQueries
from app.infra.config.database import get_db_session
from app.infra.config.dependencies import get_current_user_id
from app.infra.config.logging_config import get_logger, bind_context

router = APIRouter()
log = get_logger("api.decks.status")


@router.get("/{deck_id}/status", response_model=DeckStatusResponse)
async def get_deck_status(
    deck_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
    authorization: str | None = Header(default=None),
) -> DeckStatusResponse:
    """
    Get current status of a deck.

    This is a read-only operation that bypasses use cases and goes directly
    to the query layer following CQRS-lite pattern.
    """
    try:
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        bind_context(user_id=str(current_user_id), deck_id=str(deck_id))
        log.info("deck.status.request")
        # Use query layer for read operations (CQRS-lite)

        deck_query = DeckQueries(db_session)
        _res = deck_query.get_deck_status(deck_id, current_user_id)
        deck_info = await _res if inspect.isawaitable(_res) else _res

        if not deck_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deck not found or access denied",
            )

        response = DeckStatusResponse(
            deck_id=str(deck_info["deck_id"]),
            status=deck_info["status"],
            slide_count=deck_info["slide_count"],
            created_at=deck_info["created_at"],
            updated_at=deck_info.get("updated_at"),
            completed_at=deck_info.get("completed_at"),
        )
        log.info(
            "deck.status.success", deck_id=response.deck_id, status=response.status
        )
        return response

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        log.exception("deck.status.error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch deck status",
        )


@router.get("/{deck_id}", response_model=dict)
async def get_deck_details(
    deck_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
    authorization: str | None = Header(default=None),
) -> dict:
    """
    Get complete deck details including all slides.

    Returns the full deck structure with generated slides for completed decks.
    """
    try:
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        bind_context(user_id=str(current_user_id), deck_id=str(deck_id))
        log.info("deck.details.request")
        deck_query = DeckQueries(db_session)
        _res = deck_query.get_deck_with_slides(deck_id, current_user_id)
        deck_details = await _res if inspect.isawaitable(_res) else _res

        if not deck_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deck not found or access denied",
            )

        log.info("deck.details.success", deck_id=str(deck_id))
        return deck_details

    except HTTPException:
        raise
    except Exception as e:
        log.exception("deck.details.error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch deck details",
        )
