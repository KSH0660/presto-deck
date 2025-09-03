"""
FastAPI router for deck operations using Use Case-Driven Architecture.
"""

from uuid import UUID
import inspect
from fastapi import APIRouter, Depends, HTTPException, status, Header, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    CreateDeckRequest,
    CreateDeckResponse,
    DeckStatusResponse,
    SlideOut,
    SlideListResponse,
    InsertSlideRequest,
    ReorderSlidesRequest,
    Pagination,
    DeckEventOut,
)
from app.application.use_cases.create_deck_plan import CreateDeckPlanUseCase
from app.application.unit_of_work import UnitOfWork
from app.data.repositories.deck_repository import DeckRepository
from app.data.repositories.event_repository import EventRepository
from app.data.repositories.slide_repository import SlideRepository
from app.data.queries.deck_queries import DeckQueries
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
from app.infra.messaging.redis_client import get_redis_client
from app.infra.config.logging_config import get_logger, bind_context


router = APIRouter(prefix="/decks", tags=["decks"])
log = get_logger("api.decks")


@router.post("/", response_model=CreateDeckResponse)
async def create_deck(
    raw: dict = Body(...),
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
    arq_client: ARQClient = Depends(get_arq_client),
    ws_broadcaster: WebSocketBroadcaster = Depends(get_websocket_broadcaster),
    llm_client: LangChainClient = Depends(get_llm_client),
    authorization: str | None = Header(default=None),
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
        # Explicit header check to ensure 401 on missing auth
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        bind_context(user_id=str(current_user_id))
        log.info(
            "deck.create.request",
            prompt_len=len(raw.get("prompt", "")) if raw else 0,
            has_style=bool((raw or {}).get("style_preferences")),
        )
        # Validate payload after auth to ensure 401 precedence
        from pydantic import ValidationError

        try:
            request = CreateDeckRequest(**raw)
        except ValidationError as ve:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=ve.errors()
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
        from app.domain_core.entities.slide import Slide
        from datetime import datetime, timezone

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
                total=len(slide_outputs), limit=len(slide_outputs), offset=0
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
