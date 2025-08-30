from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class SessionRecord(Dict[str, Any]):
    pass


class Storage(ABC):
    @abstractmethod
    async def create_session(self, payload: Dict[str, Any]) -> str: ...

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[SessionRecord]: ...

    @abstractmethod
    async def update_session(
        self, session_id: str, payload: Dict[str, Any]
    ) -> None: ...

    @abstractmethod
    async def save_file(
        self, session_id: str, filename: str, content: bytes
    ) -> None: ...

    @abstractmethod
    async def list_files(self, session_id: str) -> List[str]: ...
