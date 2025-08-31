"""인메모리 덱 저장소 구현체"""

from typing import List, Optional, Dict
from app.domain.entities.deck import Deck
from app.ports.repositories.deck_repository import DeckRepository


class MemoryDeckRepository(DeckRepository):
    """인메모리 덱 저장소 구현체"""

    def __init__(self):
        self._decks: Dict[str, Deck] = {}

    async def save(self, deck: Deck) -> None:
        """덱 저장"""
        self._decks[deck.id] = deck

    async def find_by_id(self, deck_id: str) -> Optional[Deck]:
        """ID로 덱 조회"""
        return self._decks.get(deck_id)

    async def find_all(self) -> List[Deck]:
        """모든 덱 조회"""
        return list(self._decks.values())

    async def delete(self, deck_id: str) -> bool:
        """덱 삭제"""
        if deck_id in self._decks:
            del self._decks[deck_id]
            return True
        return False

    async def exists(self, deck_id: str) -> bool:
        """덱 존재 여부 확인"""
        return deck_id in self._decks
