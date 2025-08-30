"""얇은 어댑터: 파이프라인 실행기의 스트리밍 함수를 노출합니다."""

from typing import AsyncGenerator, Optional
import asyncio

from app.models.schema import GenerateRequest

from .pipeline.executor import stream_presentation as _stream


async def stream_presentation(
    req: GenerateRequest, cancel_event: Optional[asyncio.Event] = None
) -> AsyncGenerator[str, None]:
    """Plan→Select→Render 파이프라인 스트리밍.

    내부 구현은 app.core.pipeline.executor 로 위임됩니다.
    """
    async for chunk in _stream(req, cancel_event=cancel_event):
        yield chunk
