from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse

from app.core.storage.inmemory import InMemoryStorage

router = APIRouter()


def _get_storage():
    # For now, default to in-memory to keep tests hermetic.
    # RedisStorage can be selected via settings in future.
    return InMemoryStorage()


@router.post("/session")
async def create_session(
    user_prompt: str = Form(...),
    theme: Optional[str] = Form(None),
    color_preference: Optional[str] = Form(None),
    files: list[UploadFile] | None = File(None),
) -> JSONResponse:
    """Create a session with initial user request and optional files."""
    storage = _get_storage()
    sid = await storage.create_session(
        {
            "user_prompt": user_prompt,
            "theme": theme,
            "color_preference": color_preference,
        }
    )

    saved = 0
    if files:
        for f in files:
            content = await f.read()
            await storage.save_file(sid, f.filename, content)
            saved += 1

    return JSONResponse({"session_id": sid, "files_saved": saved})
