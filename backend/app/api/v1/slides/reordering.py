"""
Slide reordering operations.
"""

import inspect
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    SlideOut,
    SlideListResponse,
    ReorderSlidesRequest,
    Pagination,
)
from app.data.queries.deck_queries import DeckQueries
from app.data.repositories.slide_repository import SlideRepository
from app.infra.config.database import get_db_session
from app.infra.config.dependencies import get_current_user_id
from app.infra.config.logging_config import get_logger, bind_context

router = APIRouter()
log = get_logger("api.slides.reordering")


@router.post("/{deck_id}/reorder", response_model=SlideListResponse)
async def reorder_slides(
    deck_id: UUID,
    request: ReorderSlidesRequest,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
    authorization: str | None = Header(default=None),
) -> SlideListResponse:
    """
    Reorder slides in the deck.

    Provide a list of slide_id and their new order positions.
    """
    try:
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        bind_context(user_id=str(current_user_id), deck_id=str(deck_id))
        log.info("slides.reorder.request", count=len(request.orders))
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
        existing_slides = await slide_repo.get_by_deck_id(deck_id)

        # Create lookup map
        slide_map = {str(slide.id): slide for slide in existing_slides}

        # Validate all slide_ids exist
        for item in request.orders:
            if item.slide_id not in slide_map:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Slide {item.slide_id} not found",
                )

        # Update slide orders
        for item in request.orders:
            slide = slide_map[item.slide_id]
            slide.order = item.order
            await slide_repo.update(slide)

        await db_session.commit()

        # Return updated slide list
        updated_slides = await slide_repo.get_by_deck_id(deck_id)
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
            for slide in updated_slides
        ]

        response = SlideListResponse(
            items=slide_outputs,
            pagination=Pagination(
                total=len(slide_outputs), limit=max(1, len(slide_outputs)), offset=0
            ),
        )
        log.info("slides.reorder.success", count=len(response.items))
        return response

    except HTTPException:
        raise
    except Exception as e:
        log.exception("slides.reorder.error", error=str(e))
        await db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reorder slides",
        )
