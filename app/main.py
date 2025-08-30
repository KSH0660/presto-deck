from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.models.schema import HealthResponse, ReadyResponse
import asyncio
from contextlib import asynccontextmanager

from app.api.v1 import export as export_api
from app.api.v1 import system as system_api
from app.api.v1 import plan as plan_api
from app.api.v1 import render_modular as render_api
from app.api.v1 import sessions as sessions_api
from app.api.v1 import ui as ui_api
from app.core.infra.config import settings
from app.core.infra.metrics import metrics_router
from app.core.templates.template_manager import (
    initialize_template_data,
    get_template_summaries,
)
from app.core.infra.logging import configure_logging

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    애플리케이션의 수명 주기 동안 실행되는 컨텍스트 매니저입니다.
    서버 시작 시 템플릿 데이터 초기화를 수행합니다.
    """
    # Startup
    print("애플리케이션 시작: 템플릿 카탈로그 초기화를 시작합니다...")
    asyncio.create_task(initialize_template_data())
    print("템플릿 카탈로그 초기화 작업이 예약되었습니다.")
    yield
    # Shutdown
    print("애플리케이션이 종료됩니다.")


app = FastAPI(
    title="Presto API",
    description="AI-powered presentation slide generator.",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
origins = [
    "http://localhost",
    "http://localhost:8000",  # For local development
    "http://127.0.0.1:8000",  # For local development
    "http://localhost:5173",  # Default Vite dev server port
    "http://127.0.0.1:5173",  # Default Vite dev server port
    "*",  # Allow all origins for development, be more restrictive in production
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, PUT, DELETE, OPTIONS, etc.)
    allow_headers=["*"],  # Allow all headers
)

app.include_router(export_api.router, prefix="/api/v1")
app.include_router(system_api.router, prefix="/api/v1")
if settings.ENABLE_METRICS:
    app.include_router(metrics_router)
app.include_router(plan_api.router, prefix="/api/v1")
app.include_router(render_api.router, prefix="/api/v1")
app.include_router(sessions_api.router, prefix="/api/v1")
app.include_router(ui_api.router, prefix="/api/v1")


@app.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    """Liveness probe endpoint."""
    return {"status": "ok"}


@app.get("/readyz", response_model=ReadyResponse)
async def readyz() -> ReadyResponse:
    """Readiness probe with lightweight checks."""
    catalog = get_template_summaries()
    return {
        "status": "ready",
        "templates": len(catalog),
        "env": {"OPENAI_CONFIGURED": bool(settings.OPENAI_API_KEY)},
    }


# Mount frontend static files at root (registered last to avoid shadowing API routes)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"

if FRONTEND_DIR.exists():
    # html=True 는 index.html을 기본 문서로 제공합니다.
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIR), html=True),
        name="frontend",
    )
