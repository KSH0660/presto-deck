"""의존성 주입 컨테이너"""

from typing import Optional
from app.services.deck.deck_service import DeckService
from app.services.rendering.rendering_service import RenderingService
from app.api.v1.controllers.deck_controller import DeckController

# 저장소
from app.adapters.repositories.memory_deck_repository import MemoryDeckRepository
from app.ports.repositories.deck_repository import DeckRepository

# 이벤트
from app.adapters.events.simple_event_publisher import SimpleEventPublisher
from app.ports.events.event_publisher import EventPublisher

# 외부 서비스 (기존 코드와 연동을 위한 임시 구현체들)
from app.ports.services.llm_service import LLMService
from app.ports.services.template_service import TemplateService
from app.infrastructure.config.settings import settings


class Container:
    """의존성 주입 컨테이너"""

    def __init__(self):
        self._deck_repository: Optional[DeckRepository] = None
        self._event_publisher: Optional[EventPublisher] = None
        self._llm_service: Optional[LLMService] = None
        self._template_service: Optional[TemplateService] = None
        self._deck_service: Optional[DeckService] = None
        self._rendering_service: Optional[RenderingService] = None
        self._deck_controller: Optional[DeckController] = None

    def deck_repository(self) -> DeckRepository:
        """덱 저장소"""
        if self._deck_repository is None:
            if settings.USE_REDIS:
                # TODO: Redis 구현체로 교체
                self._deck_repository = MemoryDeckRepository()
            else:
                self._deck_repository = MemoryDeckRepository()
        return self._deck_repository

    def event_publisher(self) -> EventPublisher:
        """이벤트 발행자"""
        if self._event_publisher is None:
            self._event_publisher = SimpleEventPublisher()
        return self._event_publisher

    def llm_service(self) -> LLMService:
        """LLM 서비스"""
        if self._llm_service is None:
            # TODO: 기존 LLM 코드를 어댁터로 래핑
            from app.adapters.llm.legacy_llm_adapter import LegacyLLMAdapter

            self._llm_service = LegacyLLMAdapter()
        return self._llm_service

    def template_service(self) -> TemplateService:
        """템플릿 서비스"""
        if self._template_service is None:
            # TODO: 기존 템플릿 코드를 어댑터로 래핑
            from app.adapters.templates.legacy_template_adapter import (
                LegacyTemplateAdapter,
            )

            self._template_service = LegacyTemplateAdapter()
        return self._template_service

    def deck_service(self) -> DeckService:
        """덱 서비스"""
        if self._deck_service is None:
            self._deck_service = DeckService(
                deck_repository=self.deck_repository(),
                llm_service=self.llm_service(),
                template_service=self.template_service(),
                event_publisher=self.event_publisher(),
            )
        return self._deck_service

    def rendering_service(self) -> RenderingService:
        """렌더링 서비스"""
        if self._rendering_service is None:
            self._rendering_service = RenderingService(
                deck_repository=self.deck_repository(),
                llm_service=self.llm_service(),
                template_service=self.template_service(),
                event_publisher=self.event_publisher(),
            )
        return self._rendering_service

    def deck_controller(self) -> DeckController:
        """덱 컨트롤러"""
        if self._deck_controller is None:
            self._deck_controller = DeckController(
                deck_service=self.deck_service(),
                rendering_service=self.rendering_service(),
            )
        return self._deck_controller


# 전역 컨테이너 인스턴스
container = Container()
