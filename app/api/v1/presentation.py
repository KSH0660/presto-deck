# app/api/v1/presentation.py
import logging  # Added
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.streaming import stream_presentation
from app.models.schema import GenerateRequest

logger = logging.getLogger(__name__)  # Added

router = APIRouter()


@router.post("/generate")
async def generate_presentation(req: GenerateRequest):
    """
    Generates and streams a presentation as Server-Sent Events (SSE).

    This endpoint initiates a presentation generation process based on the user's
    prompt. It streams the results step-by-step, providing real-time updates
    to the client.

    Events Streamed:
    - `started`: Confirms the process has begun.
    - `deck_plan`: The overall plan for the presentation is ready.
    - `slide_rendered`: A single slide has been rendered.
    - `progress`: The completion progress.
    - `completed`: The entire presentation is finished.
    - `error`: An error occurred during generation.
    """

    async def event_generator():
        try:
            async for event_data in stream_presentation(req):
                yield event_data.encode("utf-8")
        except Exception as e:
            # Handle potential cancellations or unexpected errors during streaming
            logger.error(
                "Client-side error or cancellation: %s", e, exc_info=True
            )  # Changed
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
