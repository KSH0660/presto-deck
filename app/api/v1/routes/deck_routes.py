"""덱 라우터 (새 아키텍처)"""

from fastapi import APIRouter, Path, Query
from fastapi.responses import StreamingResponse
from app.api.v1.dto.deck_dto import (
    CreateDeckRequest,
    EditSlideRequest,
    DeckResponse,
    DeckListResponse,
    SlideResponse,
    DeleteResponse,
)
from app.infrastructure.container import container

router = APIRouter(prefix="/v2/decks", tags=["Decks v2 (Clean Architecture)"])


@router.post("/", summary="덱 생성")
async def create_deck(request: CreateDeckRequest) -> dict:
    """새 덱을 생성합니다."""
    controller = container.deck_controller()
    return await controller.create_deck(request)


@router.post("/{deck_id}/generate", summary="슬라이드 생성 (스트리밍)")
async def generate_slides(
    deck_id: str = Path(..., description="덱 ID"),
    quality: str = Query("default", description="품질 티어 (draft/default/premium)"),
) -> StreamingResponse:
    """덱의 슬라이드를 생성합니다 (스트리밍 응답)."""
    controller = container.deck_controller()
    return await controller.generate_slides(deck_id, quality)


@router.post("/{deck_id}/render", summary="슬라이드 렌더링 (스트리밍)")
async def render_slides(
    deck_id: str = Path(..., description="덱 ID"),
    quality: str = Query("default", description="품질 티어"),
) -> StreamingResponse:
    """덱의 슬라이드를 렌더링합니다 (스트리밍 응답)."""
    controller = container.deck_controller()
    return await controller.render_slides(deck_id, quality)


@router.get("/{deck_id}", response_model=DeckResponse, summary="덱 조회")
async def get_deck(deck_id: str = Path(..., description="덱 ID")) -> DeckResponse:
    """특정 덱을 조회합니다."""
    controller = container.deck_controller()
    return await controller.get_deck(deck_id)


@router.get("/", response_model=DeckListResponse, summary="덱 목록 조회")
async def list_decks() -> DeckListResponse:
    """모든 덱 목록을 조회합니다."""
    controller = container.deck_controller()
    return await controller.list_decks()


@router.delete("/{deck_id}", response_model=DeleteResponse, summary="덱 삭제")
async def delete_deck(deck_id: str = Path(..., description="덱 ID")) -> DeleteResponse:
    """덱을 삭제합니다."""
    controller = container.deck_controller()
    return await controller.delete_deck(deck_id)


@router.patch(
    "/{deck_id}/slides/{slide_id}",
    response_model=SlideResponse,
    summary="슬라이드 편집",
)
async def edit_slide(
    request: EditSlideRequest,
    deck_id: str = Path(..., description="덱 ID"),
    slide_id: int = Path(..., description="슬라이드 ID"),
) -> SlideResponse:
    """슬라이드를 편집합니다."""
    controller = container.deck_controller()
    return await controller.edit_slide(deck_id, slide_id, request)
