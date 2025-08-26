from fastapi import FastAPI
from app.api.v1 import presentation
from app.api.v1 import system as system_api
from app.core.config import settings
from app.core.layout_selector import load_template_catalog

app = FastAPI(
    title="Presto API",
    description="AI-powered presentation slide generator.",
    version="1.0.0",
)

app.include_router(presentation.router, prefix="/api/v1")
app.include_router(system_api.router, prefix="/api/v1")


@app.get("/")
async def read_root():
    return {"message": "Welcome to Presto API"}


@app.get("/healthz")
async def healthz():
    """Liveness probe endpoint."""
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    """Readiness probe with lightweight checks."""
    catalog = load_template_catalog()
    return {
        "status": "ready",
        "templates": len(catalog),
        "env": {"OPENAI_CONFIGURED": bool(settings.OPENAI_API_KEY)},
    }
