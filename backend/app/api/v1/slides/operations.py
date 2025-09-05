"""
Slide CRUD operations.
"""

import inspect
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import SlideOut, InsertSlideRequest
from app.data.queries.deck_queries import DeckQueries
from app.data.repositories.slide_repository import SlideRepository
from app.domain.entities.slide import Slide
from app.infra.config.database import get_db_session
from app.infra.config.dependencies import get_current_user_id
from app.infra.config.logging_config import get_logger, bind_context

router = APIRouter()
log = get_logger("api.slides.operations")


@router.post("/{deck_id}/slides", response_model=SlideOut)
async def insert_slide(
    deck_id: UUID,
    request: InsertSlideRequest,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
    authorization: str | None = Header(default=None),
) -> SlideOut:
    """
    Insert a new slide into the deck at the specified position.

    The slide will be inserted after the specified slide_id or at the given position.
    All subsequent slides will have their order incremented.
    """
    try:
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        bind_context(user_id=str(current_user_id), deck_id=str(deck_id))
        log.info(
            "slide.insert.request",
            after_slide_id=request.after_slide_id,
            position=request.position,
        )
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

        # Determine insert position
        if request.after_slide_id:
            # Find the slide to insert after
            after_slide = next(
                (s for s in existing_slides if str(s.id) == request.after_slide_id),
                None,
            )
            if not after_slide:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Reference slide not found",
                )
            insert_order = after_slide.order + 1
        elif request.position:
            insert_order = request.position
        else:
            # Insert at end
            insert_order = len(existing_slides) + 1

        # Update order of existing slides
        for slide in existing_slides:
            if slide.order >= insert_order:
                slide.order += 1
                await slide_repo.update(slide)

        # Create new slide
        template_filename = request.template_type or "content_slide.html"
        new_slide = Slide(
            id=None,
            deck_id=deck_id,
            order=insert_order,
            title="New Slide",
            content_outline=request.seed_outline or "Click to edit slide content",
            html_content=None,
            presenter_notes="",
            template_filename=template_filename,
            created_at=datetime.now(timezone.utc),
        )

        created_slide = await slide_repo.create(new_slide)
        await db_session.commit()

        response = SlideOut(
            id=str(created_slide.id),
            deck_id=str(created_slide.deck_id),
            order=created_slide.order,
            title=created_slide.title,
            content_outline=created_slide.content_outline,
            html_content=created_slide.html_content,
            presenter_notes=created_slide.presenter_notes,
            template_type=created_slide.template_filename,
            created_at=created_slide.created_at,
            updated_at=created_slide.updated_at,
        )
        log.info("slide.insert.success", slide_id=response.id, order=response.order)
        return response

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        log.exception("slide.insert.error", error=str(e))
        await db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to insert slide",
        )
