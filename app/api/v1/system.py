from fastapi import APIRouter
from app.core.config import settings
from app.core.template_manager import get_template_summaries
from app.models.schema import MetaResponse, TemplatesResponse


router = APIRouter()


@router.get("/meta", response_model=MetaResponse)
async def meta() -> MetaResponse:
    """Service metadata and operational configuration."""
    quality = {
        "draft": {
            "model": settings.DRAFT_MODEL,
            "max_concurrency": settings.DRAFT_MAX_CONCURRENCY,
        },
        "default": {
            "model": settings.DEFAULT_MODEL,
            "max_concurrency": settings.DEFAULT_MAX_CONCURRENCY,
        },
        "premium": {
            "model": settings.PREMIUM_MODEL,
            "max_concurrency": settings.PREMIUM_MAX_CONCURRENCY,
        },
    }

    catalog = get_template_summaries()
    return {
        "service": "presto-api",
        "version": "1.0.0",
        "quality_tiers": quality,
        "template_count": len(catalog),
    }


@router.get("/templates", response_model=TemplatesResponse)
async def list_templates() -> TemplatesResponse:
    """List available slide templates by filename."""
    catalog = get_template_summaries()
    return {"templates": sorted(list(catalog.keys()))}
