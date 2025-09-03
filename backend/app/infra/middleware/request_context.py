"""
Request context middleware for structured logging.
"""

from __future__ import annotations

from typing import Callable
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.infra.config.logging_config import bind_context, clear_context, get_logger


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Adds a request_id and basic request info to structlog context.

    Also logs request start/end and propagates X-Request-ID header.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:  # type: ignore[override]
        request_id = request.headers.get("x-request-id") or str(uuid4())
        client = request.client.host if request.client else None
        path = str(request.url.path)
        method = request.method

        bind_context(request_id=request_id, path=path, method=method)
        logger = get_logger("http")

        logger.info("request.start", client_ip=client)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            logger.info("request.end", status_code=response.status_code)
            return response
        except Exception as exc:  # pragma: no cover
            logger.exception("request.error", error=str(exc))
            raise
        finally:
            clear_context()
