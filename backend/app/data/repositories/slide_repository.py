"""
Slide repository for data access operations.
"""

from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from datetime import datetime, timezone

from app.data.models.slide_model import SlideModel
from app.data.models.slide_version_model import SlideVersionModel, SlideVersionReason
from app.domain_core.entities.slide import Slide
from app.infra.config.logging_config import get_logger


class SlideRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._log = get_logger("repo.slide")

    async def create(self, slide: Slide) -> Slide:
        """Create a new slide."""
        slide_model = SlideModel(
            deck_id=slide.deck_id,
            order=slide.order,
            title=slide.title,
            content_outline=slide.content_outline,
            html_content=slide.html_content,
            presenter_notes=slide.presenter_notes,
            template_filename=slide.template_filename,
            created_at=slide.created_at,
            updated_at=slide.updated_at,
        )

        self.session.add(slide_model)
        await self.session.flush()  # Get the ID without committing

        # Update entity with generated ID
        slide.id = slide_model.id
        self._log.info(
            "slide.create", slide_id=str(slide.id), deck_id=str(slide.deck_id)
        )
        return slide

    async def get_by_id(self, slide_id: UUID) -> Optional[Slide]:
        """Get slide by ID."""
        result = await self.session.execute(
            select(SlideModel).where(SlideModel.id == slide_id)
        )
        slide_model = result.scalar_one_or_none()

        if not slide_model:
            self._log.info("slide.get.not_found", slide_id=str(slide_id))
            return None

        entity = self._to_entity(slide_model)
        self._log.info("slide.get", slide_id=str(slide_id))
        return entity

    async def get_by_deck_id(self, deck_id: UUID) -> List[Slide]:
        """Get all slides for a deck ordered by slide order."""
        result = await self.session.execute(
            select(SlideModel)
            .where(SlideModel.deck_id == deck_id)
            .order_by(SlideModel.order)
        )
        slide_models = result.scalars().all()

        items = [self._to_entity(model) for model in slide_models]
        self._log.info("slide.list", deck_id=str(deck_id), count=len(items))
        return items

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
                template_filename=slide.template_filename,
                order=slide.order,
                updated_at=slide.updated_at,
            )
        )
        self._log.info("slide.update", slide_id=str(slide.id))
        return slide

    async def delete(self, slide_id: UUID) -> bool:
        """Delete a slide."""
        result = await self.session.execute(
            delete(SlideModel).where(SlideModel.id == slide_id)
        )
        deleted = result.rowcount > 0
        self._log.info("slide.delete", slide_id=str(slide_id), deleted=deleted)
        return deleted

    async def count_slides(self, deck_id: UUID) -> int:
        """Count total slides in a deck."""
        result = await self.session.execute(
            select(func.count(SlideModel.id)).where(SlideModel.deck_id == deck_id)
        )
        count = result.scalar() or 0
        self._log.info("slide.count", deck_id=str(deck_id), count=count)
        return count

    async def count_incomplete_slides(self, deck_id: UUID) -> int:
        """Count slides without HTML content."""
        result = await self.session.execute(
            select(func.count(SlideModel.id)).where(
                SlideModel.deck_id == deck_id, SlideModel.html_content.is_(None)
            )
        )
        count = result.scalar() or 0
        self._log.info("slide.count.incomplete", deck_id=str(deck_id), count=count)
        return count

    async def create_version(
        self,
        slide_id: UUID,
        deck_id: UUID,
        reason: SlideVersionReason,
        created_by: Optional[UUID] = None,
        change_description: Optional[str] = None,
        parent_version: Optional[int] = None,
    ) -> SlideVersionModel:
        """Create a new version of a slide."""
        slide_model = await self.session.get(SlideModel, slide_id)
        if not slide_model:
            raise ValueError(f"Slide {slide_id} not found")

        next_version_no = slide_model.current_version + 1

        snapshot = slide_model.get_current_snapshot()

        version_model = SlideVersionModel(
            slide_id=slide_id,
            deck_id=deck_id,
            version_no=next_version_no,
            reason=reason.value,
            snapshot=snapshot,
            created_by=created_by,
            change_description=change_description,
            parent_version=parent_version,
        )

        self.session.add(version_model)

        slide_model.current_version = next_version_no
        slide_model.updated_at = datetime.now(timezone.utc)

        await self.session.flush()
        self._log.info(
            "slide.version.create",
            slide_id=str(slide_id),
            version_no=next_version_no,
            reason=reason.value,
        )
        return version_model

    async def get_version_history(self, slide_id: UUID) -> List[SlideVersionModel]:
        """Get all versions of a slide in descending order."""
        result = await self.session.execute(
            select(SlideVersionModel)
            .where(SlideVersionModel.slide_id == slide_id)
            .order_by(SlideVersionModel.version_no.desc())
        )
        items = result.scalars().all()
        self._log.info(
            "slide.version.history", slide_id=str(slide_id), count=len(items)
        )
        return items

    async def get_version(
        self, slide_id: UUID, version_no: int
    ) -> Optional[SlideVersionModel]:
        """Get a specific version of a slide."""
        result = await self.session.execute(
            select(SlideVersionModel).where(
                SlideVersionModel.slide_id == slide_id,
                SlideVersionModel.version_no == version_no,
            )
        )
        version = result.scalar_one_or_none()
        self._log.info(
            "slide.version.get",
            slide_id=str(slide_id),
            version_no=version_no,
            found=bool(version),
        )
        return version

    async def rollback_to_version(
        self, slide_id: UUID, version_no: int, created_by: Optional[UUID] = None
    ) -> bool:
        """Rollback slide to a specific version."""
        version_model = await self.get_version(slide_id, version_no)
        if not version_model:
            return False

        slide_model = await self.session.get(SlideModel, slide_id)
        if not slide_model:
            return False

        slide_model.apply_snapshot(version_model.snapshot_data)

        await self.create_version(
            slide_id=slide_id,
            deck_id=slide_model.deck_id,
            reason=SlideVersionReason.ROLLBACK,
            created_by=created_by,
            change_description=f"Rolled back to version {version_no}",
            parent_version=version_no,
        )

        self._log.info(
            "slide.version.rollback", slide_id=str(slide_id), to_version=version_no
        )
        return True

    async def update_with_versioning(
        self,
        slide: Slide,
        reason: SlideVersionReason = SlideVersionReason.USER_EDIT,
        created_by: Optional[UUID] = None,
        change_description: Optional[str] = None,
    ) -> Slide:
        """Update slide and create a new version."""
        await self.create_version(
            slide_id=slide.id,
            deck_id=slide.deck_id,
            reason=reason,
            created_by=created_by,
            change_description=change_description,
        )

        updated = await self.update(slide)
        self._log.info(
            "slide.update.versioned", slide_id=str(slide.id), reason=reason.value
        )
        return updated

    def _to_entity(self, model: SlideModel) -> Slide:
        """Convert SQLAlchemy model to domain entity."""
        return Slide(
            id=model.id,
            deck_id=model.deck_id,
            order=model.order,
            title=model.title,
            content_outline=model.content_outline,
            html_content=model.html_content,
            presenter_notes=model.presenter_notes,
            template_filename=model.template_filename,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
