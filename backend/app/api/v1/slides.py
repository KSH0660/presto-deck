"""
FastAPI router for individual slide operations with versioning support.
"""

from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    SlideOut,
    PatchSlideRequest,
    DeleteSlideResponse,
    SlideVersionOut,
    SlideVersionListResponse,
    RevertSlideRequest,
    Pagination,
)
from app.data.repositories.slide_repository import SlideRepository
from app.data.models.slide_version_model import SlideVersionReason
from app.data.queries.deck_queries import DeckQueries
from app.infra.config.database import get_db_session
from app.infra.config.dependencies import get_current_user_id
from app.infra.config.logging_config import get_logger, bind_context
import inspect


router = APIRouter(prefix="/slides", tags=["slides"])
log = get_logger("api.slides")


@router.patch("/{slide_id}", response_model=SlideOut)
async def update_slide(
    slide_id: str,
    request: PatchSlideRequest,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
    if_match: Optional[str] = Header(
        None, alias="If-Match"
    ),  # ETag for concurrency control
    authorization: Optional[str] = Header(default=None),
) -> SlideOut:
    """
    Update slide content with automatic versioning.

    Creates a new version snapshot before applying changes.
    Supports partial updates - only provided fields are updated.

    Headers:
    - If-Match: Optional ETag for optimistic concurrency control
    """
    try:
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        bind_context(user_id=str(current_user_id), slide_id=str(slide_id))
        log.info("slide.update.request")
        slide_repo = SlideRepository(db_session)
        slide = await slide_repo.get_by_id(slide_id)

        if not slide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Slide not found",
            )

        # Verify user owns the deck
        deck_query = DeckQueries(db_session)
        _res = deck_query.get_deck_status(slide.deck_id, current_user_id)
        deck_info = await _res if inspect.isawaitable(_res) else _res

        if not deck_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deck not found or access denied",
            )

        # TODO: Implement ETag-based concurrency control with if_match header

        # Apply partial updates
        updated = False
        if request.title is not None:
            slide.title = request.title
            updated = True
        if request.content_outline is not None:
            slide.content_outline = request.content_outline
            updated = True
        if request.html_content is not None:
            slide.html_content = request.html_content
            updated = True
        if request.presenter_notes is not None:
            slide.presenter_notes = request.presenter_notes
            updated = True
        if request.template_type is not None:
            slide.template_filename = request.template_type
            updated = True

        if not updated:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided for update",
            )

        # Update with versioning
        reason = SlideVersionReason.USER_EDIT
        if request.reason:
            try:
                reason = SlideVersionReason(request.reason)
            except ValueError:
                reason = SlideVersionReason.USER_EDIT

        updated_slide = await slide_repo.update_with_versioning(
            slide=slide,
            reason=reason,
            created_by=current_user_id,
            change_description=f"Updated via API: {', '.join([k for k, v in request.model_dump().items() if v is not None and k != 'reason'])}",
        )

        await db_session.commit()

        html_val = getattr(updated_slide, "html_content", None)
        notes_val = getattr(updated_slide, "presenter_notes", None)
        response = SlideOut(
            id=str(updated_slide.id),
            deck_id=str(updated_slide.deck_id),
            order=updated_slide.order,
            title=updated_slide.title,
            content_outline=updated_slide.content_outline,
            html_content=html_val if isinstance(html_val, (str, type(None))) else None,
            presenter_notes=(
                notes_val if isinstance(notes_val, (str, type(None))) else None
            ),
            template_type=updated_slide.template_filename,
            created_at=updated_slide.created_at,
            updated_at=updated_slide.updated_at,
        )
        log.info("slide.update.success", slide_id=response.id)
        return response

    except HTTPException:
        raise
    except ValueError as e:
        log.exception("slide.update.value_error", error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        log.exception("slide.update.error", error=str(e))
        await db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update slide",
        )


@router.delete("/{slide_id}", response_model=DeleteSlideResponse)
async def delete_slide(
    slide_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
    authorization: Optional[str] = Header(default=None),
) -> DeleteSlideResponse:
    """
    Delete a slide (soft delete with versioning).

    Creates a version snapshot before marking as deleted.
    Updates the order of subsequent slides.
    """
    try:
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        bind_context(user_id=str(current_user_id), slide_id=str(slide_id))
        log.info("slide.delete.request")
        slide_repo = SlideRepository(db_session)
        slide = await slide_repo.get_by_id(slide_id)

        if not slide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Slide not found",
            )

        # Verify user owns the deck
        deck_query = DeckQueries(db_session)
        _res = deck_query.get_deck_status(slide.deck_id, current_user_id)
        deck_info = await _res if inspect.isawaitable(_res) else _res

        if not deck_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deck not found or access denied",
            )

        # Create version before deletion
        await slide_repo.create_version(
            slide_id=slide.id,
            deck_id=slide.deck_id,
            reason=SlideVersionReason.DELETE,
            created_by=current_user_id,
            change_description="Slide deleted via API",
        )

        # Get all slides in deck to update order
        all_slides = await slide_repo.get_by_deck_id(slide.deck_id)
        deleted_order = slide.order

        # Update order of subsequent slides
        for s in all_slides:
            if s.order > deleted_order:
                s.order -= 1
                await slide_repo.update(s)

        # Delete the slide (this could be soft delete in production)
        await slide_repo.delete(slide_id)
        await db_session.commit()

        log.info("slide.delete.success", slide_id=str(slide_id))
        return DeleteSlideResponse(slide_id=str(slide_id), soft_deleted=True)

    except HTTPException:
        raise
    except Exception as e:
        log.exception("slide.delete.error", error=str(e))
        await db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete slide",
        )


@router.get("/{slide_id}/versions", response_model=SlideVersionListResponse)
async def get_slide_versions(
    slide_id: UUID,
    limit: int = 20,
    offset: int = 0,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
    authorization: Optional[str] = Header(default=None),
) -> SlideVersionListResponse:
    """
    Get version history for a slide.

    Returns versions in descending order (newest first).
    """
    try:
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        bind_context(user_id=str(current_user_id), slide_id=str(slide_id))
        log.info("slide.versions.request", limit=limit, offset=offset)
        slide_repo = SlideRepository(db_session)
        slide = await slide_repo.get_by_id(slide_id)

        if not slide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Slide not found",
            )

        # Verify user owns the deck
        deck_query = DeckQueries(db_session)
        _res = deck_query.get_deck_status(slide.deck_id, current_user_id)
        deck_info = await _res if inspect.isawaitable(_res) else _res

        if not deck_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deck not found or access denied",
            )

        versions = await slide_repo.get_version_history(slide_id)

        # Apply pagination
        total = len(versions)
        paginated_versions = versions[offset : offset + limit]

        version_outputs = [
            SlideVersionOut(
                id=str(version.id),
                slide_id=str(version.slide_id),
                deck_id=str(version.deck_id),
                version_no=version.version_no,
                reason=version.reason,
                snapshot=version.snapshot_data,
                created_at=version.created_at,
                created_by=str(version.created_by) if version.created_by else None,
            )
            for version in paginated_versions
        ]

        response = SlideVersionListResponse(
            items=version_outputs,
            pagination=Pagination(total=total, limit=limit, offset=offset),
        )
        log.info("slide.versions.success", count=len(response.items))
        return response

    except HTTPException:
        raise
    except Exception as e:
        log.exception("slide.versions.error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch slide versions",
        )


@router.get("/{slide_id}/versions/{version_no}", response_model=SlideVersionOut)
async def get_slide_version(
    slide_id: UUID,
    version_no: int,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
    authorization: Optional[str] = Header(default=None),
) -> SlideVersionOut:
    """
    Get a specific version of a slide.
    """
    try:
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        bind_context(user_id=str(current_user_id), slide_id=str(slide_id))
        log.info("slide.version.request", version_no=version_no)
        slide_repo = SlideRepository(db_session)
        slide = await slide_repo.get_by_id(slide_id)

        if not slide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Slide not found",
            )

        # Verify user owns the deck
        deck_query = DeckQueries(db_session)
        _res = deck_query.get_deck_status(slide.deck_id, current_user_id)
        deck_info = await _res if inspect.isawaitable(_res) else _res

        if not deck_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deck not found or access denied",
            )

        version = await slide_repo.get_version(slide_id, version_no)

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Version not found",
            )

        response = SlideVersionOut(
            id=str(version.id),
            slide_id=str(version.slide_id),
            deck_id=str(version.deck_id),
            version_no=version.version_no,
            reason=version.reason,
            snapshot=version.snapshot_data,
            created_at=version.created_at,
            created_by=str(version.created_by) if version.created_by else None,
        )
        log.info("slide.version.success", version_no=response.version_no)
        return response

    except HTTPException:
        raise
    except Exception as e:
        log.exception("slide.version.error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch slide version",
        )


@router.post("/{slide_id}/revert", response_model=SlideOut)
async def revert_slide(
    slide_id: UUID,
    request: RevertSlideRequest,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
    authorization: Optional[str] = Header(default=None),
) -> SlideOut:
    """
    Revert slide to a specific version.

    Creates a new version entry documenting the revert action.
    """
    try:
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        bind_context(user_id=str(current_user_id), slide_id=str(slide_id))
        log.info("slide.revert.request", to_version=request.to_version)
        slide_repo = SlideRepository(db_session)
        slide = await slide_repo.get_by_id(slide_id)

        if not slide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Slide not found",
            )

        # Verify user owns the deck
        deck_query = DeckQueries(db_session)
        _res = deck_query.get_deck_status(slide.deck_id, current_user_id)
        deck_info = await _res if inspect.isawaitable(_res) else _res

        if not deck_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deck not found or access denied",
            )

        # Verify target version exists
        target_version = await slide_repo.get_version(slide_id, request.to_version)
        if not target_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version {request.to_version} not found",
            )

        # Perform rollback
        success = await slide_repo.rollback_to_version(
            slide_id=slide_id, version_no=request.to_version, created_by=current_user_id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to revert slide",
            )

        await db_session.commit()

        # Get updated slide
        updated_slide = await slide_repo.get_by_id(slide_id)

        html_val = getattr(updated_slide, "html_content", None)
        notes_val = getattr(updated_slide, "presenter_notes", None)
        response = SlideOut(
            id=str(updated_slide.id),
            deck_id=str(updated_slide.deck_id),
            order=updated_slide.order,
            title=updated_slide.title,
            content_outline=updated_slide.content_outline,
            html_content=html_val if isinstance(html_val, (str, type(None))) else None,
            presenter_notes=(
                notes_val if isinstance(notes_val, (str, type(None))) else None
            ),
            template_type=updated_slide.template_filename,
            created_at=updated_slide.created_at,
            updated_at=updated_slide.updated_at,
        )
        log.info("slide.revert.success", slide_id=response.id)
        return response

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        log.exception("slide.revert.error", error=str(e))
        await db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revert slide",
        )
