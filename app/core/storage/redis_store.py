from typing import Any, Dict, List, Optional

try:
    import redis.asyncio as redis  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    redis = None  # type: ignore

from .base import Storage, SessionRecord


class RedisStorage(Storage):  # pragma: no cover - exercised only when redis available
    def __init__(
        self, url: str = "redis://localhost:6379/0", prefix: str = "presto:"
    ) -> None:
        if redis is None:
            raise RuntimeError("redis-py not installed")
        self._r = redis.from_url(url)
        self._prefix = prefix

    def _key(self, sid: str) -> str:
        return f"{self._prefix}sessions:{sid}"

    async def create_session(self, payload: Dict[str, Any]) -> str:
        import uuid

        sid = uuid.uuid4().hex
        await self._r.hset(
            self._key(sid), mapping={"data": str(payload), "files": "[]"}
        )
        return sid

    async def get_session(self, session_id: str) -> Optional[SessionRecord]:
        raw = await self._r.hgetall(self._key(session_id))
        if not raw:
            return None
        import json

        data = json.loads(raw.get(b"data", b"{}"))
        files = json.loads(raw.get(b"files", b"[]"))
        return SessionRecord({"data": data, "files": files})

    async def update_session(self, session_id: str, payload: Dict[str, Any]) -> None:
        import json

        rec = await self.get_session(session_id) or SessionRecord(
            {"data": {}, "files": []}
        )
        rec["data"].update(payload)
        await self._r.hset(
            self._key(session_id), mapping={"data": json.dumps(rec["data"])}
        )

    async def save_file(self, session_id: str, filename: str, content: bytes) -> None:
        # Store file bytes in a separate key
        await self._r.set(f"{self._key(session_id)}:file:{filename}", content)
        rec = await self.get_session(session_id) or SessionRecord(
            {"data": {}, "files": []}
        )
        rec["files"].append(filename)
        import json

        await self._r.hset(
            self._key(session_id), mapping={"files": json.dumps(rec["files"])}
        )

    async def list_files(self, session_id: str) -> List[str]:
        rec = await self.get_session(session_id) or SessionRecord(
            {"data": {}, "files": []}
        )
        return list(rec.get("files", []))
