import asyncio
import json
from typing import Dict


async def sse_event(event: str, data: dict) -> str:
    """SSE 이벤트 포맷으로 직렬화합니다."""
    return (
        f"event: {event}\n" + "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"
    )


class EventEmitter:
    """단계에서 공통으로 사용하는 이벤트 전송기."""

    def __init__(self, queue: asyncio.Queue[str]):
        self.queue = queue

    async def emit(self, event: str, data: Dict):
        await self.queue.put(await sse_event(event, data))
