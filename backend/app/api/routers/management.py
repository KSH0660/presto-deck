"""
Deck management endpoints (cancel, etc.).
"""

import inspect
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.queries.deck_queries import DeckQueries
from app.infra.config.database import get_db_session
from app.infra.config.dependencies import get_current_user_id
from app.infra.messaging.redis_client import get_redis_client
from app.infra.config.logging_config import get_logger, bind_context

router = APIRouter()
log = get_logger("api.decks.management")


@router.post("/{deck_id}/cancel")
async def cancel_deck(
    deck_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
    authorization: str | None = Header(default=None),
) -> dict:
    """
    Cancel an in-progress deck generation.

    This sets a cancellation flag in Redis that workers check between operations.
    """
    try:
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        bind_context(user_id=str(current_user_id), deck_id=str(deck_id))
        log.info("deck.cancel.request")
        # For cancellation, we could create a CancelDeckUseCase, but for now
        # we'll implement it directly as it's a simple operation
        # Verify deck exists and belongs to user
        deck_query = DeckQueries(db_session)
        _res = deck_query.get_deck_status(deck_id, current_user_id)
        deck_info = await _res if inspect.isawaitable(_res) else _res

        if not deck_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deck not found or access denied",
            )

        # Check if deck can be cancelled
        if deck_info["status"] in ["completed", "failed", "cancelled"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel deck in {deck_info['status']} status",
            )

        # Set cancellation flag in Redis
        redis_client = await get_redis_client()
        await redis_client.setex(f"cancel_deck:{deck_id}", 3600, "true")  # 1 hour TTL

        log.info("deck.cancel.success", deck_id=str(deck_id))
        return {
            "message": "Cancellation request received. Processing will stop at the next checkpoint.",
            "deck_id": str(deck_id),
        }

    except HTTPException:
        raise
    except Exception as e:
        log.exception("deck.cancel.error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel deck",
        )
