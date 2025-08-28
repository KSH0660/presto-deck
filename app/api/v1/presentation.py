# app/api/v1/presentation.py
import logging
import asyncio
from fastapi import APIRouter, HTTPException, Form
from fastapi.responses import StreamingResponse, HTMLResponse
from app.core.streaming import stream_presentation
from app.models.schema import GenerateRequest, SlideEditRequest
from app.core.llm import make_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory store for slides (for MVP)
slides_db = []
next_slide_id = 1

EDIT_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are an expert HTML editor. A user will provide you with a snippet of HTML and a natural language instruction on how to modify it.
            Your task is to return a new, valid HTML snippet that reflects the requested changes.
            ONLY return the HTML code, without any explanations, comments, or markdown formatting.
            Ensure your output is clean and directly usable.""",
        ),
        ("human", "Here is the HTML snippet to edit:\n\n```html\n{original_html}\n```"),
        ("human", "Please make the following change: {edit_prompt}"),
    ]
)

@router.get("/slides", response_class=HTMLResponse)
async def get_slides():
    """Returns the current list of slides as HTML partials."""
    if not slides_db:
        return "<div>No slides yet. Generate a presentation to get started!</div>"
    
    # In a real app, you'd use a template engine here
    html_content = ""
    for slide in slides_db:
        html_content += f'<div id="slide-{slide["id"]}"><h3>{slide["title"]}</h3><div>{slide["html_content"]}</div></div>'
    return html_content

@router.post("/slides/new", response_class=HTMLResponse)
async def create_slide(title: str = Form(...), html_content: str = Form(...)):
    """Creates a new slide and returns the updated slide list."""
    global next_slide_id
    new_slide = {
        "id": next_slide_id,
        "title": title,
        "html_content": html_content,
        "version": 1
    }
    slides_db.append(new_slide)
    next_slide_id += 1
    return await get_slides()

@router.post("/slides/{slide_id}/edit", response_class=HTMLResponse)
async def edit_slide(slide_id: int, req: SlideEditRequest):
    """Edits a slide using an AI prompt and returns the updated slide list."""
    slide_to_edit = next((s for s in slides_db if s["id"] == slide_id), None)

    if not slide_to_edit:
        raise HTTPException(status_code=404, detail="Slide not found")

    # AI-powered editing
    llm = make_llm()
    chain = EDIT_PROMPT_TEMPLATE | llm | StrOutputParser()

    new_html = await chain.ainvoke(
        {
            "original_html": slide_to_edit["html_content"],
            "edit_prompt": req.edit_prompt,
        }
    )

    slide_to_edit["html_content"] = new_html
    slide_to_edit["version"] += 1

    return await get_slides()

@router.post("/generate")
async def generate_presentation(req: GenerateRequest):
    """
    Generates and streams a presentation as Server-Sent Events (SSE).
    """
    async def event_generator():
        try:
            async for event_data in stream_presentation(req):
                yield event_data.encode("utf-8")
        except Exception as e:
            logger.error("Client-side error or cancellation: %s", e, exc_info=True)
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
async def get_progress():
    """Streams progress updates using SSE."""
    async def progress_generator():
        steps = ["Planning", "Selecting Templates", "Rendering Slides", "Complete"]
        for step in steps:
            yield f"event: step\ndata: {step}\n\n"
            await asyncio.sleep(1) # Simulate work

    return StreamingResponse(progress_generator(), media_type="text/event-stream")

@router.get("/export/html", response_class=HTMLResponse)
async def export_html():
    """Exports all slides as a single HTML file."""
    if not slides_db:
        return "<div>No slides to export.</div>"

    full_html = "<html><head><title>Presentation</title></head><body>"
    for slide in slides_db:
        full_html += f'<div><h3>{slide["title"]}</h3>{slide["html_content"]}</div><hr>'
    full_html += "</body></html>"
    
    return full_html
