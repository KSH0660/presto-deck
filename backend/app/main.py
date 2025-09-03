"""
FastAPI application entry point for Presto Deck API.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import v1_router
from app.infra.config.settings import get_settings
from app.infra.config.logging_config import setup_logging, get_logger
from app.infra.middleware.request_context import RequestContextMiddleware

settings = get_settings()

# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="AI-powered presentation deck generation service",
    version="1.0.0",
    debug=settings.debug,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request context + logging middleware
app.add_middleware(RequestContextMiddleware)

# Include routers
app.include_router(v1_router, prefix="/api")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "Presto Deck API is running",
        "version": "1.0.0",
        "status": "healthy",
    }


@app.get("/health")
async def health_check():
    """Detailed health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": "1.0.0",
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger = get_logger("app")
    logger.info(
        "app.startup",
        app_name=settings.app_name,
        environment=settings.environment,
    )

    yield  # <-- 여기서 애플리케이션이 실행됨

    # Shutdown
    logger.info("app.shutdown", app_name=settings.app_name)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug",
    )
