"""덱 컨트롤러"""

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from app.api.v1.dto.deck_dto import (
    CreateDeckRequest,
    EditSlideRequest,
    DeckResponse,
    DeckListResponse,
    SlideResponse,
    DeleteResponse,
)
from app.services.deck.deck_service import DeckService
from app.services.rendering.rendering_service import RenderingService
from app.domain.entities.deck import Deck
from app.domain.entities.slide import Slide
from app.domain.value_objects.quality import GenerationConfig
from app.domain.exceptions.domain_exceptions import (
    DeckNotFoundError,
    SlideNotFoundError,
    DomainException,
)
import json


class DeckController:
    """덱 API 컨트롤러"""

    def __init__(self, deck_service: DeckService, rendering_service: RenderingService):
        self.deck_service = deck_service
        self.rendering_service = rendering_service

    async def create_deck(self, request: CreateDeckRequest) -> dict:
        """덱 생성"""
        try:
            config = GenerationConfig(
                quality=request.quality,
                ordered=request.ordered,
                concurrency=request.concurrency,
            )

            deck_id = await self.deck_service.create_deck(
                user_prompt=request.user_prompt, config=config
            )

            return {"deck_id": deck_id}

        except DomainException as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Internal error: {e}")

    async def generate_slides(
        self, deck_id: str, quality: str = "default"
    ) -> StreamingResponse:
        """슬라이드 생성 (스트리밍)"""
        try:
            config = GenerationConfig(quality=quality)

            async def generate_stream():
                try:
                    async for slide in self.deck_service.generate_slides(
                        deck_id, config
                    ):
                        slide_data = self._slide_to_response(slide)
                        yield f"data: {json.dumps(slide_data.dict())}\n\n"

                    yield 'data: {"status": "completed"}\n\n'

                except DomainException as e:
                    error_data = {"error": str(e)}
                    yield f"data: {json.dumps(error_data)}\n\n"

            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )

        except DeckNotFoundError:
            raise HTTPException(status_code=404, detail="Deck not found")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Internal error: {e}")

    async def render_slides(
        self, deck_id: str, quality: str = "default"
    ) -> StreamingResponse:
        """슬라이드 렌더링 (스트리밍)"""
        try:
            config = GenerationConfig(quality=quality)

            async def render_stream():
                try:
                    async for slide in self.rendering_service.render_all_slides(
                        deck_id, config
                    ):
                        slide_data = self._slide_to_response(slide)
                        yield f"data: {json.dumps(slide_data.dict())}\n\n"

                    yield 'data: {"status": "completed"}\n\n'

                except DomainException as e:
                    error_data = {"error": str(e)}
                    yield f"data: {json.dumps(error_data)}\n\n"

            return StreamingResponse(render_stream(), media_type="text/event-stream")

        except DeckNotFoundError:
            raise HTTPException(status_code=404, detail="Deck not found")

    async def get_deck(self, deck_id: str) -> DeckResponse:
        """덱 조회"""
        try:
            deck = await self.deck_service.get_deck_by_id(deck_id)
            return self._deck_to_response(deck)

        except DeckNotFoundError:
            raise HTTPException(status_code=404, detail="Deck not found")

    async def list_decks(self) -> DeckListResponse:
        """덱 목록 조회"""
        try:
            decks = await self.deck_service.list_decks()
            deck_responses = [self._deck_to_response(deck) for deck in decks]
            return DeckListResponse(decks=deck_responses)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Internal error: {e}")

    async def delete_deck(self, deck_id: str) -> DeleteResponse:
        """덱 삭제"""
        try:
            success = await self.deck_service.delete_deck(deck_id)
            if success:
                return DeleteResponse(status="deleted", id=deck_id)
            else:
                raise HTTPException(status_code=500, detail="Failed to delete deck")

        except DeckNotFoundError:
            raise HTTPException(status_code=404, detail="Deck not found")

    async def edit_slide(
        self, deck_id: str, slide_id: int, request: EditSlideRequest
    ) -> SlideResponse:
        """슬라이드 편집"""
        try:
            config = GenerationConfig()
            slide = await self.deck_service.edit_slide(
                deck_id=deck_id,
                slide_id=slide_id,
                edit_prompt=request.edit_prompt,
                config=config,
            )
            return self._slide_to_response(slide)

        except (DeckNotFoundError, SlideNotFoundError) as e:
            raise HTTPException(status_code=404, detail=str(e))
        except DomainException as e:
            raise HTTPException(status_code=400, detail=str(e))

    def _deck_to_response(self, deck: Deck) -> DeckResponse:
        """도메인 덱을 응답 DTO로 변환"""
        slides = [self._slide_to_response(slide) for slide in deck.slides]

        return DeckResponse(
            id=deck.id,
            topic=deck.metadata.topic,
            audience=deck.metadata.audience,
            theme=deck.metadata.theme,
            color_preference=deck.metadata.color_preference,
            slides=slides,
            created_at=deck.created_at,
            updated_at=deck.updated_at,
            version=deck.version,
        )

    def _slide_to_response(self, slide: Slide) -> SlideResponse:
        """도메인 슬라이드를 응답 DTO로 변환"""
        return SlideResponse(
            id=slide.id,
            title=slide.content.title,
            html_content=slide.html_content,
            version=slide.version,
            status=slide.status,
        )
