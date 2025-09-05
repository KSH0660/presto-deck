"""
Common schemas used across multiple API endpoints.

This module contains shared Pydantic models and utility schemas
that are used by multiple API endpoints.
"""

from typing import Optional
from pydantic import BaseModel, Field


class Pagination(BaseModel):
    """Standard pagination metadata for list responses."""

    total: int = Field(..., ge=0, description="Total number of items")
    limit: int = Field(..., ge=1, description="Number of items per page")
    offset: int = Field(..., ge=0, description="Number of items to skip")

    @property
    def has_more(self) -> bool:
        """Check if there are more items beyond the current page."""
        return (self.offset + self.limit) < self.total

    @property
    def current_page(self) -> int:
        """Get the current page number (1-based)."""
        return (self.offset // self.limit) + 1

    @property
    def total_pages(self) -> int:
        """Get the total number of pages."""
        return (self.total + self.limit - 1) // self.limit


class HealthCheckResponse(BaseModel):
    """Health check endpoint response."""

    status: str = Field(..., description="Service status")
    timestamp: str = Field(..., description="Current timestamp")
    version: Optional[str] = Field(None, description="Service version")
    uptime: Optional[str] = Field(None, description="Service uptime")

    # Service-specific health indicators
    database: Optional[str] = Field(None, description="Database connection status")
    redis: Optional[str] = Field(None, description="Redis connection status")
    llm_service: Optional[str] = Field(None, description="LLM service status")


class MetricsResponse(BaseModel):
    """System metrics endpoint response."""

    active_decks: int = Field(
        ..., description="Number of decks currently being processed"
    )
    total_decks_today: int = Field(..., description="Total decks created today")
    average_generation_time: Optional[float] = Field(
        None, description="Average deck generation time in seconds"
    )
    queue_size: Optional[int] = Field(None, description="Background job queue size")

    # Performance metrics
    memory_usage_mb: Optional[float] = Field(None, description="Memory usage in MB")
    cpu_usage_percent: Optional[float] = Field(None, description="CPU usage percentage")


class BackgroundJobStatus(BaseModel):
    """Status information for background jobs."""

    job_id: str = Field(..., description="Unique job identifier")
    job_type: str = Field(..., description="Type of background job")
    status: str = Field(..., description="Current job status")
    created_at: str = Field(..., description="Job creation timestamp")
    started_at: Optional[str] = Field(None, description="Job start timestamp")
    completed_at: Optional[str] = Field(None, description="Job completion timestamp")
    progress: Optional[int] = Field(
        None, ge=0, le=100, description="Job progress percentage"
    )
    error_message: Optional[str] = Field(
        None, description="Error message if job failed"
    )

    # Job-specific metadata
    deck_id: Optional[str] = Field(None, description="Associated deck ID")
    user_id: Optional[str] = Field(None, description="User who initiated the job")


class SearchFilters(BaseModel):
    """Common search and filtering parameters."""

    query: Optional[str] = Field(None, description="Search query string")
    status: Optional[str] = Field(None, description="Filter by status")
    template_type: Optional[str] = Field(None, description="Filter by template type")
    created_after: Optional[str] = Field(
        None, description="Filter by creation date (ISO format)"
    )
    created_before: Optional[str] = Field(
        None, description="Filter by creation date (ISO format)"
    )

    # Sorting
    sort_by: Optional[str] = Field("created_at", description="Field to sort by")
    sort_order: Optional[str] = Field("desc", description="Sort order: asc or desc")


class BulkOperationRequest(BaseModel):
    """Request for bulk operations on multiple items."""

    item_ids: list[str] = Field(
        ..., min_items=1, max_items=100, description="List of item IDs"
    )
    operation: str = Field(..., description="Operation to perform")
    parameters: Optional[dict] = Field(
        None, description="Operation-specific parameters"
    )


class BulkOperationResponse(BaseModel):
    """Response for bulk operations."""

    total_items: int = Field(..., description="Total number of items in request")
    successful: int = Field(..., description="Number of successfully processed items")
    failed: int = Field(..., description="Number of failed items")
    errors: list[str] = Field(
        default=[], description="List of error messages for failed items"
    )
