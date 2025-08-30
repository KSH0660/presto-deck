import asyncio
from typing import Set

from app.core.pipeline.emitter import sse_event


class EventBus:
    def __init__(self) -> None:
        self._subscribers: Set[asyncio.Queue[str]] = set()

    def subscribe(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[str]) -> None:
        self._subscribers.discard(q)

    async def publish(self, event: str, data: dict) -> None:
        payload = await sse_event(event, data)
        for q in list(self._subscribers):
            try:
                q.put_nowait(payload)
            except Exception:
                pass


ui_event_bus = EventBus()
