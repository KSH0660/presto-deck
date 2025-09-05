"""
API error handling and exception mapping.

This module provides custom exception handlers and error response formatting
for the API layer, converting domain and infrastructure errors into
appropriate HTTP responses.
"""

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from datetime import datetime
import logging

from app.api.schemas.base import ErrorResponse


logger = logging.getLogger(__name__)


class DomainError(Exception):
    """Base class for domain-specific errors."""

    def __init__(self, message: str, code: str = "DOMAIN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class DeckNotFoundError(DomainError):
    """Raised when a deck is not found."""

    def __init__(self, deck_id: str):
        super().__init__(f"Deck {deck_id} not found", "DECK_NOT_FOUND")


class SlideNotFoundError(DomainError):
    """Raised when a slide is not found."""

    def __init__(self, slide_id: str):
        super().__init__(f"Slide {slide_id} not found", "SLIDE_NOT_FOUND")


class InvalidDeckStatusError(DomainError):
    """Raised when an operation is attempted on a deck with invalid status."""

    def __init__(self, current_status: str, required_status: str = None):
        if required_status:
            message = (
                f"Deck status is {current_status}, but {required_status} is required"
            )
        else:
            message = f"Operation not allowed for deck status: {current_status}"
        super().__init__(message, "INVALID_DECK_STATUS")


class DeckGenerationError(DomainError):
    """Raised when deck generation fails."""

    def __init__(self, reason: str):
        super().__init__(f"Deck generation failed: {reason}", "DECK_GENERATION_ERROR")


class SlideContentError(DomainError):
    """Raised when slide content operations fail."""

    def __init__(self, reason: str):
        super().__init__(f"Slide content error: {reason}", "SLIDE_CONTENT_ERROR")


class TemplateError(DomainError):
    """Raised when template operations fail."""

    def __init__(self, reason: str):
        super().__init__(f"Template error: {reason}", "TEMPLATE_ERROR")


# Exception handler functions
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """
    Handle domain-specific errors.

    Args:
        request: The HTTP request
        exc: The domain error

    Returns:
        JSONResponse: Formatted error response
    """
    logger.warning(f"Domain error: {exc.code} - {exc.message}")

    # Map domain errors to appropriate HTTP status codes
    status_code_mapping = {
        "DECK_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "SLIDE_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "INVALID_DECK_STATUS": status.HTTP_400_BAD_REQUEST,
        "DECK_GENERATION_ERROR": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "SLIDE_CONTENT_ERROR": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "TEMPLATE_ERROR": status.HTTP_400_BAD_REQUEST,
    }

    status_code = status_code_mapping.get(
        exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR
    )

    error_response = ErrorResponse(
        error=exc.code, detail=exc.message, timestamp=datetime.utcnow()
    )

    return JSONResponse(status_code=status_code, content=error_response.model_dump())


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handle request validation errors.

    Args:
        request: The HTTP request
        exc: The validation error

    Returns:
        JSONResponse: Formatted error response
    """
    logger.warning(f"Validation error: {exc.errors()}")

    # Format validation errors for better readability
    formatted_errors = []
    for error in exc.errors():
        location = " -> ".join(str(loc) for loc in error["loc"])
        formatted_errors.append(f"{location}: {error['msg']}")

    error_detail = "Validation failed: " + "; ".join(formatted_errors)

    error_response = ErrorResponse(
        error="VALIDATION_ERROR", detail=error_detail, timestamp=datetime.utcnow()
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.model_dump(),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle HTTP exceptions.

    Args:
        request: The HTTP request
        exc: The HTTP exception

    Returns:
        JSONResponse: Formatted error response
    """
    logger.warning(f"HTTP exception: {exc.status_code} - {exc.detail}")

    error_response = ErrorResponse(
        error=f"HTTP_{exc.status_code}",
        detail=str(exc.detail),
        timestamp=datetime.utcnow(),
    )

    return JSONResponse(
        status_code=exc.status_code, content=error_response.model_dump()
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions.

    Args:
        request: The HTTP request
        exc: The unexpected exception

    Returns:
        JSONResponse: Generic error response
    """
    logger.exception(f"Unexpected error: {type(exc).__name__} - {str(exc)}")

    error_response = ErrorResponse(
        error="INTERNAL_SERVER_ERROR",
        detail="An unexpected error occurred. Please try again later.",
        timestamp=datetime.utcnow(),
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(),
    )


def setup_error_handlers(app) -> None:
    """
    Setup error handlers for the FastAPI application.

    Args:
        app: The FastAPI application instance
    """
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
