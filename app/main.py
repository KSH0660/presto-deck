from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from contextlib import asynccontextmanager

from app.api.v1 import presentation
from app.api.v1 import system as system_api
from app.core.config import settings
from app.core.template_manager import (
    initialize_template_data,
    get_template_summaries,
)
from app.core.logging import configure_logging

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
    catalog = get_template_summaries()
    return {
        "status": "ready",
        "templates": len(catalog),
        "env": {"OPENAI_CONFIGURED": bool(settings.OPENAI_API_KEY)},
    }
