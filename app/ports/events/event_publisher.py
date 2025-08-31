"""이벤트 발행 포트 인터페이스"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class EventPublisher(ABC):
    """이벤트 발행자 인터페이스"""

    @abstractmethod
    async def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        """이벤트 발행"""
        pass

    @abstractmethod
    async def publish_deck_created(self, deck_id: str) -> None:
        """덱 생성 이벤트"""
        pass

    @abstractmethod
    async def publish_slide_rendered(self, deck_id: str, slide_id: int) -> None:
        """슬라이드 렌더링 완료 이벤트"""
        pass

    @abstractmethod
    async def publish_deck_completed(self, deck_id: str) -> None:
        """덱 완료 이벤트"""
        pass
