import os
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .base import Storage, SessionRecord


class InMemoryStorage(Storage):
    def __init__(self, upload_dir: str = "uploads") -> None:
        self._sessions: Dict[str, SessionRecord] = {}
        self._upload_dir = upload_dir
        os.makedirs(self._upload_dir, exist_ok=True)

    async def create_session(self, payload: Dict[str, Any]) -> str:
        sid = uuid4().hex
        self._sessions[sid] = SessionRecord({"data": payload, "files": []})
        os.makedirs(os.path.join(self._upload_dir, sid), exist_ok=True)
        return sid

    async def get_session(self, session_id: str) -> Optional[SessionRecord]:
        return self._sessions.get(session_id)

    async def update_session(self, session_id: str, payload: Dict[str, Any]) -> None:
        rec = self._sessions.setdefault(
            session_id, SessionRecord({"data": {}, "files": []})
        )
        rec["data"].update(payload)

    async def save_file(self, session_id: str, filename: str, content: bytes) -> None:
        path = os.path.join(self._upload_dir, session_id)
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, filename), "wb") as f:
            f.write(content)
        rec = self._sessions.setdefault(
            session_id, SessionRecord({"data": {}, "files": []})
        )
        rec["files"].append(filename)

    async def list_files(self, session_id: str) -> List[str]:
        rec = self._sessions.get(session_id) or {}
        return list(rec.get("files", []))
