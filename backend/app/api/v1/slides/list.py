"""
Slide listing endpoints.
"""

import inspect
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import SlideOut, SlideListResponse, Pagination
from app.data.queries.deck_queries import DeckQueries
from app.data.repositories.slide_repository import SlideRepository
from app.infra.config.database import get_db_session
from app.infra.config.dependencies import get_current_user_id
from app.infra.config.logging_config import get_logger, bind_context

router = APIRouter()
log = get_logger("api.slides.list")


@router.get("/{deck_id}/slides", response_model=SlideListResponse)
async def get_deck_slides(
    deck_id: UUID,
    limit: int = 50,
    offset: int = 0,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
    authorization: str | None = Header(default=None),
) -> SlideListResponse:
    """
    Get all slides for a deck with pagination.

    Returns slides ordered by their position in the deck.
    """
    try:
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        bind_context(user_id=str(current_user_id), deck_id=str(deck_id))
        log.info("deck.slides.request", limit=limit, offset=offset)
        # Verify deck exists and belongs to user
        deck_query = DeckQueries(db_session)
        _res = deck_query.get_deck_status(deck_id, current_user_id)
        deck_info = await _res if inspect.isawaitable(_res) else _res

        if not deck_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deck not found or access denied",
            )

        slide_repo = SlideRepository(db_session)
        slides = await slide_repo.get_by_deck_id(deck_id)

        # Apply pagination
        total = len(slides)
        paginated_slides = slides[offset : offset + limit]

        slide_outputs = [
            SlideOut(
                id=str(slide.id),
                deck_id=str(slide.deck_id),
                order=slide.order,
                title=slide.title,
                content_outline=slide.content_outline,
                html_content=slide.html_content,
                presenter_notes=slide.presenter_notes,
                template_type=slide.template_filename,
                created_at=slide.created_at,
                updated_at=slide.updated_at,
            )
            for slide in paginated_slides
        ]

        response = SlideListResponse(
            items=slide_outputs,
            pagination=Pagination(total=total, limit=limit, offset=offset),
        )
        log.info("deck.slides.success", count=len(response.items))
        return response

    except HTTPException:
        raise
    except Exception as e:
        log.exception("deck.slides.error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch deck slides",
        )
