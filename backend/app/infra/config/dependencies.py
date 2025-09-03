"""
FastAPI dependency injection configuration for Use Case-Driven Architecture.
"""

from typing import Annotated, Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.config.database import get_db_session
from app.infra.messaging.arq_client import ARQClient, get_arq_client
from app.infra.messaging.websocket_broadcaster import WebSocketBroadcaster
from app.infra.llm.langchain_client import LangChainClient
from app.infra.assets.template_catalog import TemplateCatalog
from app.infra.config.settings import get_settings
from app.infra.config.logging_config import get_logger


async def get_current_user_id(
    authorization: Annotated[str, Header()] = None,
) -> UUID:
    """
    Extract user ID from JWT token.

    For now, this is a placeholder implementation.
    In production, this would validate JWT and extract user_id.
    """
    logger = get_logger("auth")
    if not authorization:
        logger.info("auth.missing_header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # TODO: Implement proper JWT validation
    # For development, return a dummy user ID
    user_id = UUID("12345678-1234-5678-9012-123456789012")
    logger.info("auth.ok", user_id=str(user_id))
    return user_id


async def verify_websocket_token(token: Optional[str]) -> Optional[UUID]:
    """
    Verify WebSocket JWT token and extract user ID.

    For WebSocket connections, tokens are typically passed as query parameters.
    """
    logger = get_logger("auth.ws")
    if not token:
        logger.info("auth.ws.no_token")
        return None

    # TODO: Implement proper JWT validation
    # For development, return a dummy user ID
    user_id = UUID("12345678-1234-5678-9012-123456789012")
    logger.info("auth.ws.ok", user_id=str(user_id))
    return user_id


async def get_websocket_broadcaster() -> WebSocketBroadcaster:
    """Dependency for WebSocket broadcaster."""
    from app.infra.messaging.redis_client import get_redis_client

    redis_client = await get_redis_client()
    return WebSocketBroadcaster(redis_client=redis_client)


async def get_llm_client() -> LangChainClient:
    """Dependency for LLM client."""
    settings = get_settings()

    # Use mock client in development when OPENAI_API_KEY is dummy
    if settings.openai_api_key == "dummy-key-for-test":
        from app.infra.llm.mock_client import MockLLMClient

        return MockLLMClient()

    return LangChainClient(
        model_name=settings.openai_model,
        temperature=0.3,
        max_tokens=4000,
    )


async def get_template_catalog() -> TemplateCatalog:
    """Dependency for template catalog."""
    settings = get_settings()
    # Assume assets are in a templates directory
    assets_path = settings.assets_path or "assets/templates"
    return TemplateCatalog(asset_dir_path=assets_path)


# Type aliases for cleaner dependency injection
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]
ARQClientDep = Annotated[ARQClient, Depends(get_arq_client)]
WebSocketBroadcasterDep = Annotated[
    WebSocketBroadcaster, Depends(get_websocket_broadcaster)
]
LLMClientDep = Annotated[LangChainClient, Depends(get_llm_client)]
TemplateCatalogDep = Annotated[TemplateCatalog, Depends(get_template_catalog)]
