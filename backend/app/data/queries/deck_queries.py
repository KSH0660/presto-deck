"""
Read-only queries for deck data (CQRS-lite).
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.data.models.deck_model import DeckModel
from app.infra.config.logging_config import get_logger


class DeckQueries:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._log = get_logger("queries.deck")

    async def get_deck_status(
        self, deck_id: UUID, user_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get deck status information for API response."""
        result = await self.session.execute(
            select(DeckModel).where(
                DeckModel.id == deck_id, DeckModel.user_id == user_id
            )
        )
        deck_model = result.scalar_one_or_none()

        if not deck_model:
            self._log.info(
                "deck.status.not_found", deck_id=str(deck_id), user_id=str(user_id)
            )
            return None

        data = {
            "deck_id": str(deck_model.id),
            "status": deck_model.status,
            "slide_count": deck_model.slide_count,
            "created_at": deck_model.created_at,
            "updated_at": deck_model.updated_at,
            "completed_at": deck_model.completed_at,
        }
        self._log.info("deck.status.found", deck_id=str(deck_id), status=data["status"])
        return data

    async def get_deck_with_slides(
        self, deck_id: UUID, user_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get deck with all slides for full presentation view."""
        result = await self.session.execute(
            select(DeckModel)
            .options(selectinload(DeckModel.slides))
            .where(DeckModel.id == deck_id, DeckModel.user_id == user_id)
        )
        deck_model = result.scalar_one_or_none()

        if not deck_model:
            self._log.info(
                "deck.details.not_found", deck_id=str(deck_id), user_id=str(user_id)
            )
            return None

        slides = [
            {
                "id": str(slide.id),
                "order": slide.order,
                "title": slide.title,
                "html_content": slide.html_content,
                "presenter_notes": slide.presenter_notes,
                "is_complete": slide.html_content is not None,
            }
            for slide in sorted(deck_model.slides, key=lambda s: s.order)
        ]

        data = {
            "deck_id": str(deck_model.id),
            "prompt": deck_model.prompt,
            "status": deck_model.status,
            "template_type": deck_model.template_type,
            "slide_count": len(slides),
            "slides": slides,
            "created_at": deck_model.created_at,
            "updated_at": deck_model.updated_at,
            "completed_at": deck_model.completed_at,
        }
        self._log.info(
            "deck.details.found", deck_id=str(deck_id), slide_count=len(slides)
        )
        return data

    async def get_user_decks_summary(self, user_id: UUID) -> List[Dict[str, Any]]:
        """Get summary of all user's decks."""
        result = await self.session.execute(
            select(DeckModel)
            .where(DeckModel.user_id == user_id)
            .order_by(DeckModel.created_at.desc())
        )
        deck_models = result.scalars().all()

        result_list = [
            {
                "deck_id": str(deck.id),
                "prompt": (
                    deck.prompt[:100] + "..." if len(deck.prompt) > 100 else deck.prompt
                ),
                "status": deck.status,
                "slide_count": deck.slide_count,
                "template_type": deck.template_type,
                "created_at": deck.created_at,
                "updated_at": deck.updated_at,
            }
            for deck in deck_models
        ]
        self._log.info(
            "deck.list.summary", count=len(result_list), user_id=str(user_id)
        )
        return result_list
