# app/api/v1/generate.py
import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.streaming import stream_presentation
from app.models.schema import GenerateRequest
from app.core.infra import state

router = APIRouter()


@router.post("/generate")
async def generate_presentation(req: GenerateRequest) -> StreamingResponse:
    """프레젠테이션을 생성하고 SSE로 실시간 스트림합니다."""
    state.slides_db.clear()
    state.reset_slide_ids(1)

    async def event_generator():
        cancel_event = asyncio.Event()
        try:
            async for event_data in stream_presentation(req, cancel_event=cancel_event):
                yield event_data.encode("utf-8")
        except asyncio.CancelledError:
            cancel_event.set()
            raise
        except Exception:
            # client disconnect or other error
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/progress", response_class=StreamingResponse)
async def get_progress() -> StreamingResponse:
    """SSE로 진행 상황을 순차적으로 전송합니다 (데모)."""

    async def progress_generator():
        steps = ["Planning", "Selecting Templates", "Rendering Slides", "Complete"]
        for step in steps:
            yield f"event: step\ndata: {step}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(progress_generator(), media_type="text/event-stream")
