"""
Deck events endpoints for polling-based updates.
"""

import inspect
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import DeckEventOut
from app.data.queries.deck_queries import DeckQueries
from app.infra.config.database import get_db_session
from app.infra.config.dependencies import get_current_user_id
from app.infra.config.logging_config import get_logger, bind_context

router = APIRouter()
log = get_logger("api.decks.events")


@router.get("/{deck_id}/events", response_model=list[DeckEventOut])
async def get_deck_events(
    deck_id: UUID,
    since_version: int = 0,
    limit: int = 100,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
    authorization: str | None = Header(default=None),
) -> list[DeckEventOut]:
    """
    Get deck events for polling-based updates (alternative to WebSocket).

    Use since_version parameter to get only new events since last check.
    """
    try:
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        bind_context(user_id=str(current_user_id), deck_id=str(deck_id))
        log.info("deck.events.request", since_version=since_version, limit=limit)
        # Verify deck exists and belongs to user
        deck_query = DeckQueries(db_session)
        _res = deck_query.get_deck_status(deck_id, current_user_id)
        deck_info = await _res if inspect.isawaitable(_res) else _res

        if not deck_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deck not found or access denied",
            )

        # For now, return empty list - this would integrate with event sourcing
        # In a full implementation, this would query the deck_events table
        log.info("deck.events.success", items=0)
        return []

    except HTTPException:
        raise
    except Exception as e:
        log.exception("deck.events.error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch deck events",
        )
