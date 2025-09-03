"""
Read-only queries for slide data (CQRS-lite).
"""

from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.data.models.slide_model import SlideModel


class SlideQueries:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_slide_content(
        self, slide_id: UUID, deck_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get slide content for presentation."""
        result = await self.session.execute(
            select(SlideModel).where(
                SlideModel.id == slide_id, SlideModel.deck_id == deck_id
            )
        )
        slide_model = result.scalar_one_or_none()

        if not slide_model:
            return None

        return {
            "slide_id": str(slide_model.id),
            "order": slide_model.order,
            "title": slide_model.title,
            "html_content": slide_model.html_content,
            "presenter_notes": slide_model.presenter_notes,
            "template_type": slide_model.template_type,
            "is_complete": slide_model.html_content is not None,
        }

    async def get_slides_progress(self, deck_id: UUID) -> List[Dict[str, Any]]:
        """Get progress summary of all slides in deck."""
        result = await self.session.execute(
            select(SlideModel)
            .where(SlideModel.deck_id == deck_id)
            .order_by(SlideModel.order)
        )
        slide_models = result.scalars().all()

        return [
            {
                "slide_id": str(slide.id),
                "order": slide.order,
                "title": slide.title,
                "is_complete": slide.html_content is not None,
                "content_length": len(slide.html_content or ""),
                "updated_at": slide.updated_at,
            }
            for slide in slide_models
        ]
