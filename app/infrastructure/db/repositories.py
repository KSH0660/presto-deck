from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.observability import metrics
from app.domain.entities import Deck, DeckEvent, Slide
from app.domain.repositories import DeckRepository, EventRepository, SlideRepository
from app.infrastructure.db.models import DeckEventModel, DeckModel, SlideModel


class PostgresDeckRepository(DeckRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, deck: Deck) -> Deck:
        try:
            db_deck = DeckModel(
                id=deck.id,
                user_id=deck.user_id,
                title=deck.title,
                status=deck.status.value,
                version=deck.version,
                deck_plan=deck.deck_plan,
                created_at=deck.created_at,
                updated_at=deck.updated_at,
            )
            self.session.add(db_deck)
            await self.session.flush()

            metrics.record_database_operation("create", "decks", "success")
            return deck
        except Exception:
            metrics.record_database_operation("create", "decks", "error")
            raise

    async def get_by_id(self, deck_id: UUID) -> Optional[Deck]:
        try:
            result = await self.session.execute(
                select(DeckModel)
                .options(selectinload(DeckModel.slides))
                .where(DeckModel.id == deck_id)
            )
            db_deck = result.scalar_one_or_none()

            metrics.record_database_operation("get", "decks", "success")

            if db_deck is None:
                return None

            return Deck(
                id=db_deck.id,
                user_id=db_deck.user_id,
                title=db_deck.title,
                status=db_deck.status.value,
                version=db_deck.version,
                deck_plan=db_deck.deck_plan,
                created_at=db_deck.created_at,
                updated_at=db_deck.updated_at,
            )
        except Exception:
            metrics.record_database_operation("get", "decks", "error")
            raise

    async def get_by_user_id(
        self, user_id: str, limit: int = 10, offset: int = 0
    ) -> List[Deck]:
        try:
            result = await self.session.execute(
                select(DeckModel)
                .where(DeckModel.user_id == user_id)
                .order_by(desc(DeckModel.created_at))
                .limit(limit)
                .offset(offset)
            )
            db_decks = result.scalars().all()

            metrics.record_database_operation("list", "decks", "success")

            return [
                Deck(
                    id=db_deck.id,
                    user_id=db_deck.user_id,
                    title=db_deck.title,
                    status=db_deck.status.value,
                    version=db_deck.version,
                    deck_plan=db_deck.deck_plan,
                    created_at=db_deck.created_at,
                    updated_at=db_deck.updated_at,
                )
                for db_deck in db_decks
            ]
        except Exception:
            metrics.record_database_operation("list", "decks", "error")
            raise

    async def update(self, deck: Deck) -> Deck:
        try:
            result = await self.session.execute(
                select(DeckModel).where(DeckModel.id == deck.id)
            )
            db_deck = result.scalar_one_or_none()

            if db_deck is None:
                metrics.record_database_operation("update", "decks", "not_found")
                raise ValueError(f"Deck with ID {deck.id} not found")

            db_deck.title = deck.title
            db_deck.status = deck.status.value
            db_deck.version = deck.version
            db_deck.deck_plan = deck.deck_plan
            db_deck.updated_at = deck.updated_at

            await self.session.flush()

            metrics.record_database_operation("update", "decks", "success")
            return deck
        except ValueError:
            raise
        except Exception:
            metrics.record_database_operation("update", "decks", "error")
            raise

    async def delete(self, deck_id: UUID) -> bool:
        try:
            result = await self.session.execute(
                select(DeckModel).where(DeckModel.id == deck_id)
            )
            db_deck = result.scalar_one_or_none()

            if db_deck is None:
                metrics.record_database_operation("delete", "decks", "not_found")
                return False

            await self.session.delete(db_deck)
            await self.session.flush()

            metrics.record_database_operation("delete", "decks", "success")
            return True
        except Exception:
            metrics.record_database_operation("delete", "decks", "error")
            raise

    async def exists(self, deck_id: UUID) -> bool:
        try:
            result = await self.session.execute(
                select(func.count(DeckModel.id)).where(DeckModel.id == deck_id)
            )
            count = result.scalar()

            metrics.record_database_operation("exists", "decks", "success")
            return count > 0
        except Exception:
            metrics.record_database_operation("exists", "decks", "error")
            raise

    async def is_owned_by_user(self, deck_id: UUID, user_id: str) -> bool:
        try:
            result = await self.session.execute(
                select(func.count(DeckModel.id)).where(
                    and_(DeckModel.id == deck_id, DeckModel.user_id == user_id)
                )
            )
            count = result.scalar()

            metrics.record_database_operation("ownership_check", "decks", "success")
            return count > 0
        except Exception:
            metrics.record_database_operation("ownership_check", "decks", "error")
            raise


class PostgresSlideRepository(SlideRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, slide: Slide) -> Slide:
        try:
            db_slide = SlideModel(
                id=slide.id,
                deck_id=slide.deck_id,
                slide_order=slide.slide_order,
                html_content=slide.html_content,
                presenter_notes=slide.presenter_notes,
                created_at=slide.created_at,
                updated_at=slide.updated_at,
            )
            self.session.add(db_slide)
            await self.session.flush()

            metrics.record_database_operation("create", "slides", "success")
            return slide
        except Exception:
            metrics.record_database_operation("create", "slides", "error")
            raise

    async def get_by_id(self, slide_id: UUID) -> Optional[Slide]:
        try:
            result = await self.session.execute(
                select(SlideModel).where(SlideModel.id == slide_id)
            )
            db_slide = result.scalar_one_or_none()

            metrics.record_database_operation("get", "slides", "success")

            if db_slide is None:
                return None

            return Slide(
                id=db_slide.id,
                deck_id=db_slide.deck_id,
                slide_order=db_slide.slide_order,
                html_content=db_slide.html_content,
                presenter_notes=db_slide.presenter_notes,
                created_at=db_slide.created_at,
                updated_at=db_slide.updated_at,
            )
        except Exception:
            metrics.record_database_operation("get", "slides", "error")
            raise

    async def get_by_deck_id(self, deck_id: UUID) -> List[Slide]:
        try:
            result = await self.session.execute(
                select(SlideModel)
                .where(SlideModel.deck_id == deck_id)
                .order_by(SlideModel.slide_order)
            )
            db_slides = result.scalars().all()

            metrics.record_database_operation("list", "slides", "success")

            return [
                Slide(
                    id=db_slide.id,
                    deck_id=db_slide.deck_id,
                    slide_order=db_slide.slide_order,
                    html_content=db_slide.html_content,
                    presenter_notes=db_slide.presenter_notes,
                    created_at=db_slide.created_at,
                    updated_at=db_slide.updated_at,
                )
                for db_slide in db_slides
            ]
        except Exception:
            metrics.record_database_operation("list", "slides", "error")
            raise

    async def update(self, slide: Slide) -> Slide:
        try:
            result = await self.session.execute(
                select(SlideModel).where(SlideModel.id == slide.id)
            )
            db_slide = result.scalar_one_or_none()
            if db_slide is None:
                metrics.record_database_operation("update", "slides", "not_found")
                raise ValueError(f"Slide with ID {slide.id} not found")

            db_slide.slide_order = slide.slide_order
            db_slide.html_content = slide.html_content
            db_slide.presenter_notes = slide.presenter_notes
            db_slide.updated_at = slide.updated_at

            await self.session.flush()

            metrics.record_database_operation("update", "slides", "success")
            return slide

        except ValueError:
            raise
        except Exception as e:
            metrics.record_database_operation(
                "update", "slides", "error", exception_type=e.__class__.__name__
            )
            raise

    async def delete(self, slide_id: UUID) -> bool:
        try:
            result = await self.session.execute(
                select(SlideModel).where(SlideModel.id == slide_id)
            )
            db_slide = result.scalar_one_or_none()

            if db_slide is None:
                metrics.record_database_operation("delete", "slides", "not_found")
                return False

            await self.session.delete(db_slide)
            await self.session.flush()

            metrics.record_database_operation("delete", "slides", "success")
            return True
        except Exception:
            metrics.record_database_operation("delete", "slides", "error")
            raise

    async def delete_by_deck_id(self, deck_id: UUID) -> int:
        try:
            result = await self.session.execute(
                select(SlideModel).where(SlideModel.deck_id == deck_id)
            )
            slides = result.scalars().all()

            count = len(slides)
            for slide in slides:
                await self.session.delete(slide)

            await self.session.flush()

            metrics.record_database_operation("delete_by_deck", "slides", "success")
            return count
        except Exception:
            metrics.record_database_operation("delete_by_deck", "slides", "error")
            raise

    async def get_max_order(self, deck_id: UUID) -> int:
        try:
            result = await self.session.execute(
                select(func.coalesce(func.max(SlideModel.slide_order), 0)).where(
                    SlideModel.deck_id == deck_id
                )
            )
            max_order = result.scalar()

            metrics.record_database_operation("max_order", "slides", "success")
            return max_order or 0
        except Exception:
            metrics.record_database_operation("max_order", "slides", "error")
            raise


class PostgresEventRepository(EventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, event: DeckEvent) -> DeckEvent:
        try:
            # Create the model instance without passing id (let database auto-generate)
            db_event = DeckEventModel(
                deck_id=event.deck_id,
                version=event.version,
                event_type=event.event_type,
                payload=event.payload,
                created_at=event.created_at,
            )
            self.session.add(db_event)
            await self.session.flush()

            # Update the event with the generated ID
            event.id = db_event.id

            metrics.record_database_operation("create", "deck_events", "success")
            return event
        except Exception:
            metrics.record_database_operation("create", "deck_events", "error")
            raise

    async def get_by_deck_id(
        self, deck_id: UUID, from_version: int = 0
    ) -> List[DeckEvent]:
        try:
            result = await self.session.execute(
                select(DeckEventModel)
                .where(
                    and_(
                        DeckEventModel.deck_id == deck_id,
                        DeckEventModel.version > from_version,
                    )
                )
                .order_by(DeckEventModel.version)
            )
            db_events = result.scalars().all()

            metrics.record_database_operation("list", "deck_events", "success")

            return [
                DeckEvent(
                    id=db_event.id,
                    deck_id=db_event.deck_id,
                    version=db_event.version,
                    event_type=db_event.event_type,
                    payload=db_event.payload,
                    created_at=db_event.created_at,
                )
                for db_event in db_events
            ]
        except Exception:
            metrics.record_database_operation("list", "deck_events", "error")
            raise

    async def get_latest_version(self, deck_id: UUID) -> int:
        try:
            result = await self.session.execute(
                select(func.coalesce(func.max(DeckEventModel.version), 0)).where(
                    DeckEventModel.deck_id == deck_id
                )
            )
            latest_version = result.scalar()

            metrics.record_database_operation(
                "latest_version", "deck_events", "success"
            )
            return latest_version or 0
        except Exception:
            metrics.record_database_operation("latest_version", "deck_events", "error")
            raise
