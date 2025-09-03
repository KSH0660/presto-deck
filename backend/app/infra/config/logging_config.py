"""
Structlog configuration and helpers.
"""

from __future__ import annotations

import logging
from typing import Optional

import structlog


def setup_logging(
    log_level: Optional[str] = None, log_format: Optional[str] = None
) -> None:
    """Configure structlog for the application.

    Args:
        log_level: Optional log level name (e.g., "INFO"). Defaults from settings.
        log_format: "json" or "console". Defaults from settings.
    """
    try:
        from app.infra.config.settings import get_settings

        settings = get_settings()
        level_name = (log_level or settings.log_level or "INFO").upper()
        fmt = (log_format or settings.log_format or "json").lower()
    except Exception:
        # Fallback if settings import fails early in startup
        level_name = (log_level or "INFO").upper()
        fmt = (log_format or "json").lower()

    level = getattr(logging, level_name, logging.INFO)

    # Configure stdlib logging so 3rd-party libs also log
    logging.basicConfig(level=level)

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
    ]

    renderer = (
        structlog.processors.JSONRenderer(sort_keys=True)
        if fmt == "json"
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:  # type: ignore[name-defined]
    """Get a structlog logger bound with a name."""
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()


def bind_context(**kwargs) -> None:
    """Bind contextvars for correlation (e.g., request_id, deck_id, user_id)."""
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear bound contextvars (call at end of request)."""
    structlog.contextvars.clear_contextvars()
