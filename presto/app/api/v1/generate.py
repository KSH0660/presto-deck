import asyncio
import json
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from presto.app.models.presentation import PresentationRequest
from presto.app.services.template import TemplateService
from presto.app.services.presentation import PresentationService
from presto.app.services.resource import ResourceService # New import


router = APIRouter()

async def presentation_generator(request: PresentationRequest, presentation_service: PresentationService):
    """A generator function that yields presentation slides one by one."""
    try:
        async for event_data in presentation_service.generate_slides_stream(request):
            yield event_data
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        error_event = {"type": "error", "data": {"message": f"An unexpected error occurred: {str(e)}"}}
        yield f"data: {json.dumps(error_event)}"

@router.post("/generate", response_class=StreamingResponse, tags=["presentation"])
async def generate_presentation_stream(
    request: PresentationRequest,
    template_service: TemplateService = Depends(TemplateService),
    resource_service: ResourceService = Depends(ResourceService), # New dependency
):
    """
    Creates a new presentation by streaming the results slide by slide.
    Uses Server-Sent Events (SSE).
    """
    presentation_service = PresentationService(template_service, resource_service) # Pass resource_service
    return StreamingResponse(presentation_generator(request, presentation_service), media_type="text/event-stream")
