from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from presto.app.api.v1 import generate, themes

app = FastAPI(
    title="Presto API", description="AI-powered presentation generator", version="1.0.0"
)

# API Routers
app.include_router(generate.router, prefix="/api/v1")
app.include_router(themes.router, prefix="/api/v1")

# Static Files
# Note: The path to the frontend directory is relative to the project root.
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "../../frontend")

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", response_class=FileResponse)
async def read_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if not os.path.exists(index_path):
        return {"error": "index.html not found"}  # Should not happen
    return FileResponse(index_path)
