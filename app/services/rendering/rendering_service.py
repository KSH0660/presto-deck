"""렌더링 서비스"""

from typing import AsyncIterator
from app.domain.entities.deck import Deck
from app.domain.entities.slide import Slide
from app.domain.value_objects.quality import GenerationConfig
from app.domain.exceptions.domain_exceptions import (
    DeckNotFoundError,
    SlideNotFoundError,
    RenderingFailedError,
)
from app.ports.repositories.deck_repository import DeckRepository
from app.ports.services.llm_service import LLMService
from app.ports.services.template_service import TemplateService
from app.ports.events.event_publisher import EventPublisher
import asyncio


class RenderingService:
    """렌더링 서비스 - 슬라이드 렌더링 전용 유스케이스"""

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

    async def render_all_slides(
        self, deck_id: str, config: GenerationConfig
    ) -> AsyncIterator[Slide]:
        """덱의 모든 슬라이드 렌더링"""
        deck = await self._get_deck(deck_id)

        if deck.is_empty:
            return

        # 동시 렌더링 제한
        semaphore = asyncio.Semaphore(config.concurrency or 3)

        async def render_single_slide(slide: Slide) -> Slide:
            async with semaphore:
                try:
                    template_names = await self.template_service.select_templates(
                        slide.content
                    )
                    rendered_slide = await self.llm_service.render_slide(
                        slide, template_names, config
                    )

                    # 덱 업데이트
                    deck.update_slide(slide.id, rendered_slide)
                    await self.deck_repository.save(deck)

                    # 이벤트 발행
                    await self.event_publisher.publish_slide_rendered(deck_id, slide.id)

                    return rendered_slide

                except Exception as e:
                    slide.mark_as_failed()
                    deck.update_slide(slide.id, slide)
                    await self.deck_repository.save(deck)
                    raise RenderingFailedError(
                        f"Failed to render slide {slide.id}: {e}"
                    )

        # 병렬 렌더링 실행
        tasks = [render_single_slide(slide) for slide in deck.slides if slide.is_draft]

        if config.ordered:
            # 순서 보장
            for task in tasks:
                rendered_slide = await task
                yield rendered_slide
        else:
            # 완료 순서대로
            for coro in asyncio.as_completed(tasks):
                try:
                    rendered_slide = await coro
                    yield rendered_slide
                except RenderingFailedError:
                    # 실패한 슬라이드는 건너뛰고 계속 진행
                    continue

    async def render_slide_by_id(
        self, deck_id: str, slide_id: int, config: GenerationConfig
    ) -> Slide:
        """특정 슬라이드만 렌더링"""
        deck = await self._get_deck(deck_id)
        slide = deck.get_slide(slide_id)

        if not slide:
            raise SlideNotFoundError(f"Slide {slide_id} not found in deck {deck_id}")

        # 템플릿 선택
        template_names = await self.template_service.select_templates(slide.content)

        try:
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

        except Exception as e:
            slide.mark_as_failed()
            deck.update_slide(slide_id, slide)
            await self.deck_repository.save(deck)
            raise RenderingFailedError(f"Failed to render slide {slide_id}: {e}")

    async def re_render_failed_slides(
        self, deck_id: str, config: GenerationConfig
    ) -> AsyncIterator[Slide]:
        """실패한 슬라이드들 재렌더링"""
        deck = await self._get_deck(deck_id)
        failed_slides = [slide for slide in deck.slides if slide.status == "failed"]

        if not failed_slides:
            return

        for slide in failed_slides:
            try:
                # 다시 draft 상태로 변경
                slide.status = "draft"

                # 재렌더링
                rendered_slide = await self.render_slide_by_id(
                    deck_id, slide.id, config
                )
                yield rendered_slide

            except RenderingFailedError:
                # 여전히 실패하면 건너뛰기
                continue

    async def _get_deck(self, deck_id: str) -> Deck:
        """덱 조회 헬퍼"""
        deck = await self.deck_repository.find_by_id(deck_id)
        if not deck:
            raise DeckNotFoundError(f"Deck {deck_id} not found")
        return deck
