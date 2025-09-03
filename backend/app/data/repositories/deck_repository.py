"""
Deck repository for data access operations.
"""

from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.data.models.deck_model import DeckModel
from app.domain_core.entities.deck import Deck


class DeckRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

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
        return deck

    async def get_by_id(self, deck_id: UUID) -> Optional[Deck]:
        """Get deck by ID."""
        result = await self.session.execute(
            select(DeckModel).where(DeckModel.id == deck_id)
        )
        deck_model = result.scalar_one_or_none()

        if not deck_model:
            return None

        return self._to_entity(deck_model)

    async def get_by_user_id(self, user_id: UUID) -> List[Deck]:
        """Get all decks for a user."""
        result = await self.session.execute(
            select(DeckModel)
            .where(DeckModel.user_id == user_id)
            .order_by(DeckModel.created_at.desc())
        )
        deck_models = result.scalars().all()

        return [self._to_entity(model) for model in deck_models]

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
        return deck

    async def delete(self, deck_id: UUID) -> bool:
        """Delete a deck."""
        result = await self.session.execute(
            delete(DeckModel).where(DeckModel.id == deck_id)
        )
        return result.rowcount > 0

    def _to_entity(self, model: DeckModel) -> Deck:
        """Convert SQLAlchemy model to domain entity."""
        from app.domain_core.value_objects.deck_status import DeckStatus
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
