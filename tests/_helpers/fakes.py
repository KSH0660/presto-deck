"""Fake repository implementations for testing."""

from typing import Dict, List, Optional
from uuid import UUID

from app.domain.entities import Deck, DeckEvent, Slide
from app.domain.repositories import DeckRepository, EventRepository, SlideRepository


class FakeDeckRepository(DeckRepository):
    """In-memory fake implementation of DeckRepository for testing."""

    def __init__(self) -> None:
        self._decks: Dict[UUID, Deck] = {}

    async def create(self, deck: Deck) -> Deck:
        self._decks[deck.id] = deck
        return deck

    async def get_by_id(self, deck_id: UUID) -> Optional[Deck]:
        return self._decks.get(deck_id)

    async def get_by_user_id(self, user_id: str, limit: int = 10, offset: int = 0) -> List[Deck]:
        user_decks = [deck for deck in self._decks.values() if deck.user_id == user_id]
        # Sort by created_at descending (newest first)
        user_decks.sort(key=lambda x: x.created_at, reverse=True)
        return user_decks[offset:offset + limit]

    async def update(self, deck: Deck) -> Deck:
        if deck.id not in self._decks:
            raise ValueError(f"Deck {deck.id} not found")
        self._decks[deck.id] = deck
        return deck

    async def delete(self, deck_id: UUID) -> bool:
        if deck_id in self._decks:
            del self._decks[deck_id]
            return True
        return False

    async def exists(self, deck_id: UUID) -> bool:
        return deck_id in self._decks

    async def is_owned_by_user(self, deck_id: UUID, user_id: str) -> bool:
        deck = self._decks.get(deck_id)
        return deck is not None and deck.user_id == user_id


class FakeSlideRepository(SlideRepository):
    """In-memory fake implementation of SlideRepository for testing."""

    def __init__(self) -> None:
        self._slides: Dict[UUID, Slide] = {}

    async def create(self, slide: Slide) -> Slide:
        self._slides[slide.id] = slide
        return slide

    async def get_by_id(self, slide_id: UUID) -> Optional[Slide]:
        return self._slides.get(slide_id)

    async def get_by_deck_id(self, deck_id: UUID) -> List[Slide]:
        deck_slides = [slide for slide in self._slides.values() if slide.deck_id == deck_id]
        # Sort by slide_order
        deck_slides.sort(key=lambda x: x.slide_order)
        return deck_slides

    async def update(self, slide: Slide) -> Slide:
        if slide.id not in self._slides:
            raise ValueError(f"Slide {slide.id} not found")
        self._slides[slide.id] = slide
        return slide

    async def delete(self, slide_id: UUID) -> bool:
        if slide_id in self._slides:
            del self._slides[slide_id]
            return True
        return False

    async def delete_by_deck_id(self, deck_id: UUID) -> int:
        slides_to_delete = [slide_id for slide_id, slide in self._slides.items() 
                           if slide.deck_id == deck_id]
        for slide_id in slides_to_delete:
            del self._slides[slide_id]
        return len(slides_to_delete)

    async def get_max_order(self, deck_id: UUID) -> int:
        deck_slides = await self.get_by_deck_id(deck_id)
        if not deck_slides:
            return 0
        return max(slide.slide_order for slide in deck_slides)


class FakeEventRepository(EventRepository):
    """In-memory fake implementation of EventRepository for testing."""

    def __init__(self) -> None:
        self.events: List[DeckEvent] = []
        self._next_id = 1

    async def create(self, event: DeckEvent) -> DeckEvent:
        event.id = self._next_id
        self._next_id += 1
        self.events.append(event)
        return event

    async def get_by_deck_id(self, deck_id: UUID, from_version: int = 0) -> List[DeckEvent]:
        deck_events = [event for event in self.events 
                      if event.deck_id == deck_id and event.version > from_version]
        # Sort by version
        deck_events.sort(key=lambda x: x.version)
        return deck_events

    async def get_latest_version(self, deck_id: UUID) -> int:
        deck_events = [event for event in self.events if event.deck_id == deck_id]
        if not deck_events:
            return 0
        return max(event.version for event in deck_events)