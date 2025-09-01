from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from app.domain.entities import Deck, DeckEvent, Slide


class DeckRepository(ABC):
    @abstractmethod
    async def create(self, deck: Deck) -> Deck:
        pass

    @abstractmethod
    async def get_by_id(self, deck_id: UUID) -> Optional[Deck]:
        pass

    @abstractmethod
    async def get_by_user_id(self, user_id: str, limit: int = 10, offset: int = 0) -> List[Deck]:
        pass

    @abstractmethod
    async def update(self, deck: Deck) -> Deck:
        pass

    @abstractmethod
    async def delete(self, deck_id: UUID) -> bool:
        pass

    @abstractmethod
    async def exists(self, deck_id: UUID) -> bool:
        pass

    @abstractmethod
    async def is_owned_by_user(self, deck_id: UUID, user_id: str) -> bool:
        pass


class SlideRepository(ABC):
    @abstractmethod
    async def create(self, slide: Slide) -> Slide:
        pass

    @abstractmethod
    async def get_by_id(self, slide_id: UUID) -> Optional[Slide]:
        pass

    @abstractmethod
    async def get_by_deck_id(self, deck_id: UUID) -> List[Slide]:
        pass

    @abstractmethod
    async def update(self, slide: Slide) -> Slide:
        pass

    @abstractmethod
    async def delete(self, slide_id: UUID) -> bool:
        pass

    @abstractmethod
    async def delete_by_deck_id(self, deck_id: UUID) -> int:
        pass

    @abstractmethod
    async def get_max_order(self, deck_id: UUID) -> int:
        pass


class EventRepository(ABC):
    @abstractmethod
    async def create(self, event: DeckEvent) -> DeckEvent:
        pass

    @abstractmethod
    async def get_by_deck_id(self, deck_id: UUID, from_version: int = 0) -> List[DeckEvent]:
        pass

    @abstractmethod
    async def get_latest_version(self, deck_id: UUID) -> int:
        pass