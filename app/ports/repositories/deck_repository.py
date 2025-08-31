"""덱 저장소 포트 인터페이스"""

from abc import ABC, abstractmethod
from typing import List, Optional
from app.domain.entities.deck import Deck


class DeckRepository(ABC):
    """덱 저장소 인터페이스"""

    @abstractmethod
    async def save(self, deck: Deck) -> None:
        """덱 저장"""
        pass

    @abstractmethod
    async def find_by_id(self, deck_id: str) -> Optional[Deck]:
        """ID로 덱 조회"""
        pass

    @abstractmethod
    async def find_all(self) -> List[Deck]:
        """모든 덱 조회"""
        pass

    @abstractmethod
    async def delete(self, deck_id: str) -> bool:
        """덱 삭제"""
        pass

    @abstractmethod
    async def exists(self, deck_id: str) -> bool:
        """덱 존재 여부 확인"""
        pass
