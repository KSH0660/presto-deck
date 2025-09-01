from contextlib import asynccontextmanager
from typing import AsyncGenerator
import json
from datetime import datetime, UTC

import structlog
from arq import ArqRedis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from app.api.schemas import HealthResponse, ErrorResponse
from app.api.v1.decks import router as decks_router
from app.api.websocket import websocket_endpoint, WebSocketManager
from app.core.config import settings
from app.core.dependencies import database, redis_client, arq_redis
from app.core.logging import setup_logging, get_logger
from app.core.observability import setup_observability
from app.infrastructure.db.database import Database
from app.infrastructure.messaging.redis_client import RedisClient, RedisPubSubManager

logger = get_logger(__name__)


class CustomJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            default=jsonable_encoder,
        ).encode("utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    await startup_event(app)
    
    try:
        yield
    finally:
        # Shutdown
        await shutdown_event(app)


async def startup_event(app: FastAPI) -> None:
    """Initialize application dependencies."""
    global database, redis_client, arq_redis
    
    logger.info("Starting up Presto-Deck API", version=settings.version)
    
    try:
        # Setup observability
        setup_observability()
        
        # Initialize database
        database = Database(settings.database_url, settings.database_echo)
        await database.initialize()
        
        # Initialize Redis
        redis_client = RedisClient(settings.redis_url)
        await redis_client.initialize()
        
        # Initialize ARQ Redis client
        arq_redis = ArqRedis.from_url(settings.get_redis_arq_url())
        
        # Initialize WebSocket manager
        redis_pubsub = RedisPubSubManager(redis_client)
        from app.api.websocket import connection_manager
        connection_manager = WebSocketManager(redis_pubsub)
        
        # Health check
        db_healthy = await database.health_check()
        redis_healthy = await redis_client.health_check()
        
        if not db_healthy:
            raise RuntimeError("Database health check failed")
        if not redis_healthy:
            raise RuntimeError("Redis health check failed")
        
        logger.info(
            "Application startup completed successfully",
            database_healthy=db_healthy,
            redis_healthy=redis_healthy,
            environment=settings.environment
        )
        
    except Exception as e:
        logger.error("Application startup failed", error=str(e))
        raise


async def shutdown_event(app: FastAPI) -> None:
    """Cleanup application resources."""
    logger.info("Shutting down Presto-Deck API")
    
    try:
        # Close connections
        if database:
            await database.close()
        
        if redis_client:
            await redis_client.close()
        
        if arq_redis:
            await arq_redis.close()
        
        logger.info("Application shutdown completed")
        
    except Exception as e:
        logger.error("Error during shutdown", error=str(e))


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    # Setup logging first
    setup_logging()
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="AI-powered presentation deck generation service",
        docs_url="/docs" if not settings.is_production() else None,
        redoc_url="/redoc" if not settings.is_production() else None,
        lifespan=lifespan,
        default_response_class=CustomJSONResponse,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_cors_origins_list(),
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(decks_router, prefix="/api/v1")
    
    # WebSocket endpoint
    app.add_websocket_route("/ws/decks/{deck_id}", websocket_endpoint)
    
    # Health check endpoint
    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """Health check endpoint."""
        services = {}
        
        if database:
            services["database"] = await database.health_check()
        
        if redis_client:
            services["redis"] = await redis_client.health_check()
        
        all_healthy = all(services.values()) if services else False
        
        return HealthResponse(
            status="healthy" if all_healthy else "unhealthy",
            timestamp=datetime.now(UTC),
            services=services,
            version=settings.version,
        )
    
    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.error(
            "Unhandled exception",
            error=str(exc),
            path=str(request.url.path),
            method=request.method,
        )
        
        return CustomJSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="internal_server_error",
                message="An unexpected error occurred",
            ).dict(),
        )
    
    return app


# Create the application instance
app = create_app()

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development(),
        log_level=settings.log_level.lower(),
    )
