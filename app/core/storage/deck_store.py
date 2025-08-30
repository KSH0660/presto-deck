from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.models.schema import DeckPlan
from app.core.infra.config import settings
import logging

try:  # optional dependency
    import redis.asyncio as redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None  # type: ignore


class DeckStore:
    async def create_deck(self, plan: DeckPlan) -> str: ...
    async def list_decks(self) -> List[Dict[str, Any]]: ...
    async def get_deck_plan(self, deck_id: str) -> Optional[DeckPlan]: ...
    async def update_deck_plan(self, deck_id: str, plan: DeckPlan) -> None: ...

    async def add_or_update_slide(
        self, deck_id: str, slide: Dict[str, Any]
    ) -> None: ...
    async def get_slide(
        self, deck_id: str, slide_id: int
    ) -> Optional[Dict[str, Any]]: ...
    async def list_slides(self, deck_id: str) -> List[Dict[str, Any]]: ...
    async def delete_slide(self, deck_id: str, slide_id: int) -> None: ...


logger = logging.getLogger(__name__)


class InMemoryDeckStore(DeckStore):
    def __init__(self) -> None:
        self._decks: Dict[str, Dict[str, Any]] = {}

    async def create_deck(self, plan: DeckPlan) -> str:
        deck_id = uuid4().hex
        self._decks[deck_id] = {
            "plan": plan.model_dump(),
            "slides": {},  # id -> slide dict
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
        }
        logger.info(
            "[DeckStore] InMemory: created deck id=%s topic=%s", deck_id, plan.topic
        )
        return deck_id

    async def list_decks(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for did, rec in self._decks.items():
            plan = DeckPlan(**rec["plan"]) if rec.get("plan") else None
            out.append(
                {
                    "id": did,
                    "topic": getattr(plan, "topic", None),
                    "audience": getattr(plan, "audience", None),
                    "slides": len(rec.get("slides", {})),
                    "created_at": rec.get("created_at"),
                    "updated_at": rec.get("updated_at"),
                }
            )
        # most recent first
        out.sort(key=lambda r: r.get("updated_at") or 0, reverse=True)
        return out

    async def get_deck_plan(self, deck_id: str) -> Optional[DeckPlan]:
        rec = self._decks.get(deck_id)
        if not rec:
            return None
        return DeckPlan(**rec["plan"]) if rec.get("plan") else None

    async def update_deck_plan(self, deck_id: str, plan: DeckPlan) -> None:
        rec = self._decks.setdefault(deck_id, {"slides": {}})
        rec["plan"] = plan.model_dump()
        rec["updated_at"] = int(time.time())
        logger.debug("[DeckStore] InMemory: updated plan deck id=%s", deck_id)

    async def add_or_update_slide(self, deck_id: str, slide: Dict[str, Any]) -> None:
        rec = self._decks.setdefault(deck_id, {"slides": {}})
        slides = rec.setdefault("slides", {})
        slides[int(slide["id"])] = slide
        rec["updated_at"] = int(time.time())
        logger.debug(
            "[DeckStore] InMemory: upsert slide deck id=%s slide_id=%s title=%s",
            deck_id,
            slide.get("id"),
            slide.get("title"),
        )

    async def get_slide(self, deck_id: str, slide_id: int) -> Optional[Dict[str, Any]]:
        rec = self._decks.get(deck_id)
        if not rec:
            return None
        return rec.get("slides", {}).get(int(slide_id))

    async def list_slides(self, deck_id: str) -> List[Dict[str, Any]]:
        rec = self._decks.get(deck_id)
        if not rec:
            return []
        slides = list((rec.get("slides") or {}).values())
        slides.sort(key=lambda s: int(s.get("id", 0)))
        return slides

    async def delete_slide(self, deck_id: str, slide_id: int) -> None:
        rec = self._decks.get(deck_id)
        if not rec:
            return
        rec.get("slides", {}).pop(int(slide_id), None)
        rec["updated_at"] = int(time.time())
        logger.debug(
            "[DeckStore] InMemory: delete slide deck id=%s slide_id=%s",
            deck_id,
            slide_id,
        )


class RedisDeckStore(DeckStore):  # pragma: no cover - depends on redis
    def __init__(self, url: str, prefix: str = "presto:") -> None:
        if redis is None:
            raise RuntimeError("redis-py not installed")
        self._r = redis.from_url(url)
        self._prefix = prefix
        logger.info("[DeckStore] Using RedisDeckStore url=%s prefix=%s", url, prefix)

    def _deck_key(self, deck_id: str) -> str:
        return f"{self._prefix}decks:{deck_id}"

    def _slides_key(self, deck_id: str) -> str:
        return f"{self._prefix}decks:{deck_id}:slides"

    def _slide_key(self, deck_id: str, slide_id: int) -> str:
        return f"{self._prefix}decks:{deck_id}:slide:{slide_id}"

    async def create_deck(self, plan: DeckPlan) -> str:
        deck_id = uuid4().hex
        await self._r.hset(
            self._deck_key(deck_id),
            mapping={
                "plan": json.dumps(plan.model_dump()),
                "created_at": str(int(time.time())),
                "updated_at": str(int(time.time())),
            },
        )
        await self._r.sadd(f"{self._prefix}decks:index", deck_id)
        logger.info(
            "[DeckStore] Redis: created deck id=%s topic=%s", deck_id, plan.topic
        )
        return deck_id

    async def list_decks(self) -> List[Dict[str, Any]]:
        deck_ids = await self._r.smembers(f"{self._prefix}decks:index")
        out: List[Dict[str, Any]] = []
        for b_id in deck_ids:
            did = b_id.decode() if isinstance(b_id, (bytes, bytearray)) else str(b_id)
            raw = await self._r.hgetall(self._deck_key(did))
            if not raw:
                continue
            plan_raw = raw.get(b"plan")
            plan = DeckPlan(**json.loads(plan_raw)) if plan_raw else None
            slides = await self._r.scard(self._slides_key(did))
            out.append(
                {
                    "id": did,
                    "topic": getattr(plan, "topic", None),
                    "audience": getattr(plan, "audience", None),
                    "slides": int(slides or 0),
                    "created_at": int(raw.get(b"created_at", b"0")),
                    "updated_at": int(raw.get(b"updated_at", b"0")),
                }
            )
        out.sort(key=lambda r: r.get("updated_at") or 0, reverse=True)
        return out

    async def get_deck_plan(self, deck_id: str) -> Optional[DeckPlan]:
        raw = await self._r.hget(self._deck_key(deck_id), "plan")
        if not raw:
            return None
        return DeckPlan(**json.loads(raw))

    async def update_deck_plan(self, deck_id: str, plan: DeckPlan) -> None:
        await self._r.hset(
            self._deck_key(deck_id),
            mapping={
                "plan": json.dumps(plan.model_dump()),
                "updated_at": str(int(time.time())),
            },
        )
        logger.debug("[DeckStore] Redis: updated plan deck id=%s", deck_id)

    async def add_or_update_slide(self, deck_id: str, slide: Dict[str, Any]) -> None:
        sid = int(slide["id"])  # type: ignore
        await self._r.hset(
            self._slide_key(deck_id, sid),
            mapping={
                k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                for k, v in slide.items()
            },
        )
        await self._r.sadd(self._slides_key(deck_id), sid)
        await self._r.hset(
            self._deck_key(deck_id), mapping={"updated_at": str(int(time.time()))}
        )
        logger.debug(
            "[DeckStore] Redis: upsert slide deck id=%s slide_id=%s title=%s",
            deck_id,
            slide.get("id"),
            slide.get("title"),
        )

    async def get_slide(self, deck_id: str, slide_id: int) -> Optional[Dict[str, Any]]:
        raw = await self._r.hgetall(self._slide_key(deck_id, slide_id))
        if not raw:
            return None
        out: Dict[str, Any] = {}
        for k, v in raw.items():
            key = k.decode() if isinstance(k, (bytes, bytearray)) else str(k)
            val_s = v.decode() if isinstance(v, (bytes, bytearray)) else str(v)
            # try json
            try:
                out[key] = json.loads(val_s)
            except Exception:
                # attempt int for id/version
                if key in ("id", "version"):
                    try:
                        out[key] = int(val_s)
                        continue
                    except Exception:
                        pass
                out[key] = val_s
        return out

    async def list_slides(self, deck_id: str) -> List[Dict[str, Any]]:
        ids = await self._r.smembers(self._slides_key(deck_id))
        out: List[Dict[str, Any]] = []
        for b_id in ids:
            sid = int(b_id)
            s = await self.get_slide(deck_id, sid)
            if s:
                out.append(s)
        out.sort(key=lambda s: int(s.get("id", 0)))
        return out

    async def delete_slide(self, deck_id: str, slide_id: int) -> None:
        await self._r.delete(self._slide_key(deck_id, slide_id))
        await self._r.srem(self._slides_key(deck_id), slide_id)
        await self._r.hset(
            self._deck_key(deck_id), mapping={"updated_at": str(int(time.time()))}
        )
        logger.debug(
            "[DeckStore] Redis: delete slide deck id=%s slide_id=%s", deck_id, slide_id
        )


_deck_store_singleton: Optional[DeckStore] = None


def get_deck_store() -> DeckStore:
    global _deck_store_singleton
    if _deck_store_singleton is not None:
        return _deck_store_singleton
    if settings.USE_REDIS and redis is not None:
        try:
            _deck_store_singleton = RedisDeckStore(settings.REDIS_URL)
            logger.info("[DeckStore] Initialized Redis store (USE_REDIS=True)")
            return _deck_store_singleton
        except Exception as e:  # pragma: no cover
            logger.warning(
                "[DeckStore] Failed to init Redis store at %s, falling back to in-memory: %s",
                settings.REDIS_URL,
                e,
            )
    _deck_store_singleton = InMemoryDeckStore()
    logger.info(
        "[DeckStore] Using InMemory store (USE_REDIS=%s, redis_lib=%s)",
        settings.USE_REDIS,
        bool(redis),
    )
    return _deck_store_singleton
