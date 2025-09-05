"""
Deck management router.

This module provides endpoints for deck operations:
- POST /decks: Create new decks and initiate generation
- GET /decks/{deck_id}: Get deck status and details
- GET /decks: List user's decks with pagination
- PUT /decks/{deck_id}/complete: Mark deck as completed
- DELETE /decks/{deck_id}: Cancel/delete decks
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import (
    get_current_user,
    get_create_deck_use_case,
    get_complete_deck_use_case,
    verify_deck_ownership,
)
from app.api.schemas.deck_io import (
    CreateDeckRequest,
    CreateDeckResponse,
    DeckStatusResponse,
    DeckListResponse,
    DeckDetailsResponse,
    CancelDeckRequest,
    CancelDeckResponse,
)
from app.api.schemas.common import Pagination
from app.application.use_cases.create_deck_plan import CreateDeckPlanUseCase
from app.application.use_cases.complete_deck import CompleteDeckUseCase
from app.api.errors import DeckNotFoundError, InvalidDeckStatusError


router = APIRouter(prefix="/decks", tags=["decks"])


@router.post(
    "/", response_model=CreateDeckResponse, status_code=status.HTTP_201_CREATED
)
async def create_deck(
    request: CreateDeckRequest,
    current_user: UUID = Depends(get_current_user),
    use_case: CreateDeckPlanUseCase = Depends(get_create_deck_use_case),
) -> CreateDeckResponse:
    """
    Create a new deck and initiate generation.

    This endpoint:
    1. Validates the deck creation request
    2. Selects appropriate template type
    3. Creates the deck entity
    4. Initiates background generation pipeline
    5. Returns deck ID and initial status

    Args:
        request: Deck creation request with prompt and preferences
        current_user: Authenticated user ID
        use_case: Deck creation use case

    Returns:
        CreateDeckResponse: Deck ID and status
    """
    try:
        result = await use_case.execute(
            user_id=current_user,
            prompt=request.prompt,
            style_preferences=request.style_preferences,
        )

        return CreateDeckResponse(
            deck_id=result["deck_id"],
            status=result["status"],
            message=result["message"],
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{deck_id}", response_model=DeckDetailsResponse)
async def get_deck_details(
    deck_id: UUID,
    current_user: UUID = Depends(get_current_user),
    _: UUID = Depends(verify_deck_ownership),
) -> DeckDetailsResponse:
    """
    Get detailed information about a specific deck.

    Args:
        deck_id: ID of the deck to retrieve
        current_user: Authenticated user ID
        _: Deck ownership verification dependency

    Returns:
        DeckDetailsResponse: Complete deck information

    Raises:
        HTTPException: If deck not found or access denied
    """
    # TODO: Implement deck details retrieval
    # This would use a query service or use case to get deck details
    # For now, return a placeholder
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Deck details endpoint not yet implemented",
    )


@router.get("/", response_model=DeckListResponse)
async def list_user_decks(
    current_user: UUID = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100, description="Number of decks per page"),
    offset: int = Query(0, ge=0, description="Number of decks to skip"),
) -> DeckListResponse:
    """
    List decks belonging to the current user.

    Args:
        current_user: Authenticated user ID
        limit: Maximum number of decks to return
        offset: Number of decks to skip for pagination

    Returns:
        DeckListResponse: Paginated list of deck summaries
    """
    # TODO: Implement deck listing
    # This would use a query service to get paginated deck list
    # For now, return empty list
    return DeckListResponse(
        items=[], pagination=Pagination(total=0, limit=limit, offset=offset)
    )


@router.put("/{deck_id}/complete", response_model=DeckStatusResponse)
async def complete_deck(
    deck_id: UUID,
    current_user: UUID = Depends(get_current_user),
    _: UUID = Depends(verify_deck_ownership),
    use_case: CompleteDeckUseCase = Depends(get_complete_deck_use_case),
) -> DeckStatusResponse:
    """
    Mark a deck as completed.

    This endpoint finalizes deck generation and marks it as ready for use.
    Only decks in GENERATING or EDITING status can be completed.

    Args:
        deck_id: ID of the deck to complete
        current_user: Authenticated user ID
        _: Deck ownership verification dependency
        use_case: Deck completion use case

    Returns:
        DeckStatusResponse: Updated deck status

    Raises:
        HTTPException: If deck cannot be completed
    """
    try:
        result = await use_case.execute(deck_id=deck_id, user_id=current_user)

        if not result["success"]:
            raise InvalidDeckStatusError(result["message"])

        return DeckStatusResponse(
            deck_id=result["deck_id"],
            status=result["status"],
            slide_count=result["slide_count"],
            completed_at=result.get("completed_at"),
        )

    except ValueError:
        raise DeckNotFoundError(str(deck_id))


@router.delete("/{deck_id}", response_model=CancelDeckResponse)
async def cancel_deck(
    deck_id: UUID,
    request: CancelDeckRequest,
    current_user: UUID = Depends(get_current_user),
    _: UUID = Depends(verify_deck_ownership),
) -> CancelDeckResponse:
    """
    Cancel deck generation or delete a deck.

    This endpoint can:
    - Cancel ongoing deck generation
    - Delete completed decks
    - Clean up associated resources

    Args:
        deck_id: ID of the deck to cancel/delete
        request: Cancellation request with optional reason
        current_user: Authenticated user ID
        _: Deck ownership verification dependency

    Returns:
        CancelDeckResponse: Cancellation confirmation

    Raises:
        HTTPException: If deck cannot be cancelled/deleted
    """
    # TODO: Implement deck cancellation/deletion
    # This would use a use case to handle cancellation logic
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Deck cancellation endpoint not yet implemented",
    )
