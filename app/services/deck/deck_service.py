"""덱 관리 서비스"""

from typing import List, AsyncIterator
from app.domain.entities.deck import Deck
from app.domain.entities.slide import Slide
from app.domain.value_objects.quality import GenerationConfig
from app.domain.exceptions.domain_exceptions import (
    DeckNotFoundError,
    SlideNotFoundError,
)
from app.ports.repositories.deck_repository import DeckRepository
from app.ports.services.llm_service import LLMService
from app.ports.services.template_service import TemplateService
from app.ports.events.event_publisher import EventPublisher
import uuid
from datetime import datetime


class DeckService:
    """덱 관리 서비스 - 덱 생성, 수정, 조회 유스케이스"""

    def __init__(
        self,
        deck_repository: DeckRepository,
        llm_service: LLMService,
        template_service: TemplateService,
        event_publisher: EventPublisher,
    ):
        self.deck_repository = deck_repository
        self.llm_service = llm_service
        self.template_service = template_service
        self.event_publisher = event_publisher

    async def create_deck(self, user_prompt: str, config: GenerationConfig) -> str:
        """새 덱 생성"""
        # 1. 덱 계획 수립
        metadata = await self.llm_service.plan_deck(user_prompt, config)

        # 2. 덱 생성
        deck_id = str(uuid.uuid4())
        deck = Deck(
            id=deck_id, metadata=metadata, created_at=datetime.now().isoformat()
        )

        # 3. 저장
        await self.deck_repository.save(deck)

        # 4. 이벤트 발행
        await self.event_publisher.publish_deck_created(deck_id)

        return deck_id

    async def generate_slides(
        self, deck_id: str, config: GenerationConfig
    ) -> AsyncIterator[Slide]:
        """덱의 슬라이드 생성"""
        deck = await self.get_deck_by_id(deck_id)

        # LLM으로 슬라이드 생성
        async for slide in self.llm_service.generate_slides(deck.metadata, config):
            deck.add_slide(slide)
            await self.deck_repository.save(deck)
            yield slide

        # 완료 이벤트 발행
        await self.event_publisher.publish_deck_completed(deck_id)

    async def render_slide(
        self, deck_id: str, slide_id: int, config: GenerationConfig
    ) -> Slide:
        """슬라이드 렌더링"""
        deck = await self.get_deck_by_id(deck_id)
        slide = deck.get_slide(slide_id)

        if not slide:
            raise SlideNotFoundError(f"Slide {slide_id} not found in deck {deck_id}")

        # 템플릿 선택
        template_names = await self.template_service.select_templates(slide.content)

        # 렌더링
        rendered_slide = await self.llm_service.render_slide(
            slide, template_names, config
        )

        # 업데이트
        deck.update_slide(slide_id, rendered_slide)
        await self.deck_repository.save(deck)

        # 이벤트 발행
        await self.event_publisher.publish_slide_rendered(deck_id, slide_id)

        return rendered_slide

    async def edit_slide(
        self, deck_id: str, slide_id: int, edit_prompt: str, config: GenerationConfig
    ) -> Slide:
        """슬라이드 편집"""
        deck = await self.get_deck_by_id(deck_id)
        slide = deck.get_slide(slide_id)

        if not slide:
            raise SlideNotFoundError(f"Slide {slide_id} not found in deck {deck_id}")

        # 편집
        edited_slide = await self.llm_service.edit_slide(slide, edit_prompt, config)

        # 업데이트
        deck.update_slide(slide_id, edited_slide)
        deck.updated_at = datetime.now().isoformat()
        await self.deck_repository.save(deck)

        return edited_slide

    async def get_deck_by_id(self, deck_id: str) -> Deck:
        """덱 조회"""
        deck = await self.deck_repository.find_by_id(deck_id)
        if not deck:
            raise DeckNotFoundError(f"Deck {deck_id} not found")
        return deck

    async def list_decks(self) -> List[Deck]:
        """모든 덱 목록 조회"""
        return await self.deck_repository.find_all()

    async def delete_deck(self, deck_id: str) -> bool:
        """덱 삭제"""
        if not await self.deck_repository.exists(deck_id):
            raise DeckNotFoundError(f"Deck {deck_id} not found")

        return await self.deck_repository.delete(deck_id)
