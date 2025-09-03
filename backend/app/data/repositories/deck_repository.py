"""
Deck repository for data access operations.
"""

from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.data.models.deck_model import DeckModel
from app.domain_core.entities.deck import Deck
from app.infra.config.logging_config import get_logger


class DeckRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._log = get_logger("repo.deck")

    async def create(self, deck: Deck) -> Deck:
        """Create a new deck."""
        deck_model = DeckModel(
            id=deck.id,
            user_id=deck.user_id,
            prompt=deck.prompt,
            status=deck.status.value,
            style_preferences=deck.style_preferences,
            template_type=deck.template_type.value if deck.template_type else None,
            slide_count=deck.slide_count,
            created_at=deck.created_at,
            updated_at=deck.updated_at,
            completed_at=deck.completed_at,
        )

        self.session.add(deck_model)
        await self.session.flush()  # Get the ID without committing

        # Update entity with generated ID if needed
        deck.id = deck_model.id
        self._log.info("deck.create", deck_id=str(deck.id), user_id=str(deck.user_id))
        return deck

    async def get_by_id(self, deck_id: UUID) -> Optional[Deck]:
        """Get deck by ID."""
        result = await self.session.execute(
            select(DeckModel).where(DeckModel.id == deck_id)
        )
        deck_model = result.scalar_one_or_none()

        if not deck_model:
            self._log.info("deck.get.not_found", deck_id=str(deck_id))
            return None

        entity = self._to_entity(deck_model)
        self._log.info("deck.get", deck_id=str(deck_id))
        return entity

    async def get_by_user_id(self, user_id: UUID) -> List[Deck]:
        """Get all decks for a user."""
        result = await self.session.execute(
            select(DeckModel)
            .where(DeckModel.user_id == user_id)
            .order_by(DeckModel.created_at.desc())
        )
        deck_models = result.scalars().all()

        items = [self._to_entity(model) for model in deck_models]
        self._log.info("deck.list", count=len(items), user_id=str(user_id))
        return items

    async def update(self, deck: Deck) -> Deck:
        """Update an existing deck."""
        await self.session.execute(
            update(DeckModel)
            .where(DeckModel.id == deck.id)
            .values(
                status=deck.status.value,
                template_type=deck.template_type.value if deck.template_type else None,
                slide_count=deck.slide_count,
                updated_at=deck.updated_at,
                completed_at=deck.completed_at,
            )
        )
        self._log.info("deck.update", deck_id=str(deck.id), status=deck.status.value)
        return deck

    async def delete(self, deck_id: UUID) -> bool:
        """Delete a deck."""
        result = await self.session.execute(
            delete(DeckModel).where(DeckModel.id == deck_id)
        )
        deleted = result.rowcount > 0
        self._log.info("deck.delete", deck_id=str(deck_id), deleted=deleted)
        return deleted

    def _to_entity(self, model: DeckModel) -> Deck:
        """Convert SQLAlchemy model to domain entity."""
        from app.api.schemas import DeckStatus
        from app.domain_core.value_objects.template_type import TemplateType

        return Deck(
            id=model.id,
            user_id=model.user_id,
            prompt=model.prompt,
            status=DeckStatus(model.status),
            style_preferences=model.style_preferences or {},
            template_type=(
                TemplateType(model.template_type) if model.template_type else None
            ),
            slide_count=model.slide_count,
            created_at=model.created_at,
            updated_at=model.updated_at,
            completed_at=model.completed_at,
        )
