"""단순 이벤트 발행자 구현체"""

from typing import Any, Dict
from app.ports.events.event_publisher import EventPublisher
import logging

logger = logging.getLogger(__name__)


class SimpleEventPublisher(EventPublisher):
    """단순 이벤트 발행자 구현체 (로깅 기반)"""

    async def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        """이벤트 발행"""
        logger.info(f"Event published: {event_type}", extra={"payload": payload})

    async def publish_deck_created(self, deck_id: str) -> None:
        """덱 생성 이벤트"""
        await self.publish("deck.created", {"deck_id": deck_id})

    async def publish_slide_rendered(self, deck_id: str, slide_id: int) -> None:
        """슬라이드 렌더링 완료 이벤트"""
        await self.publish("slide.rendered", {"deck_id": deck_id, "slide_id": slide_id})

    async def publish_deck_completed(self, deck_id: str) -> None:
        """덱 완료 이벤트"""
        await self.publish("deck.completed", {"deck_id": deck_id})
