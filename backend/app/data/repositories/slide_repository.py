"""
Slide repository for data access operations.
"""

from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func

from app.data.models.slide_model import SlideModel
from app.domain_core.entities.slide import Slide


class SlideRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, slide: Slide) -> Slide:
        """Create a new slide."""
        slide_model = SlideModel(
            deck_id=slide.deck_id,
            order=slide.order,
            title=slide.title,
            content_outline=slide.content_outline,
            html_content=slide.html_content,
            presenter_notes=slide.presenter_notes,
            template_type=slide.template_type.value,
            created_at=slide.created_at,
            updated_at=slide.updated_at,
        )

        self.session.add(slide_model)
        await self.session.flush()  # Get the ID without committing

        # Update entity with generated ID
        slide.id = slide_model.id
        return slide

    async def get_by_id(self, slide_id: UUID) -> Optional[Slide]:
        """Get slide by ID."""
        result = await self.session.execute(
            select(SlideModel).where(SlideModel.id == slide_id)
        )
        slide_model = result.scalar_one_or_none()

        if not slide_model:
            return None

        return self._to_entity(slide_model)

    async def get_by_deck_id(self, deck_id: UUID) -> List[Slide]:
        """Get all slides for a deck ordered by slide order."""
        result = await self.session.execute(
            select(SlideModel)
            .where(SlideModel.deck_id == deck_id)
            .order_by(SlideModel.order)
        )
        slide_models = result.scalars().all()

        return [self._to_entity(model) for model in slide_models]

    async def update(self, slide: Slide) -> Slide:
        """Update an existing slide."""
        await self.session.execute(
            update(SlideModel)
            .where(SlideModel.id == slide.id)
            .values(
                title=slide.title,
                content_outline=slide.content_outline,
                html_content=slide.html_content,
                presenter_notes=slide.presenter_notes,
                updated_at=slide.updated_at,
            )
        )
        return slide

    async def delete(self, slide_id: UUID) -> bool:
        """Delete a slide."""
        result = await self.session.execute(
            delete(SlideModel).where(SlideModel.id == slide_id)
        )
        return result.rowcount > 0

    async def count_slides(self, deck_id: UUID) -> int:
        """Count total slides in a deck."""
        result = await self.session.execute(
            select(func.count(SlideModel.id)).where(SlideModel.deck_id == deck_id)
        )
        return result.scalar() or 0

    async def count_incomplete_slides(self, deck_id: UUID) -> int:
        """Count slides without HTML content."""
        result = await self.session.execute(
            select(func.count(SlideModel.id)).where(
                SlideModel.deck_id == deck_id, SlideModel.html_content.is_(None)
            )
        )
        return result.scalar() or 0

    def _to_entity(self, model: SlideModel) -> Slide:
        """Convert SQLAlchemy model to domain entity."""
        from app.domain_core.value_objects.template_type import TemplateType

        return Slide(
            id=model.id,
            deck_id=model.deck_id,
            order=model.order,
            title=model.title,
            content_outline=model.content_outline,
            html_content=model.html_content,
            presenter_notes=model.presenter_notes,
            template_type=TemplateType(model.template_type),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
