"""
Utilities for managing LLM cache in testing and development workflows.

Provides convenient functions for test setup, cache inspection, and debugging.
"""

import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.infra.config.settings import get_settings
from app.infra.llm.cache_manager import get_cache_manager, clear_llm_cache
from app.infra.config.logging_config import get_logger


class LLMCacheInspector:
    """Inspector for analyzing and debugging LLM cache contents."""

    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger("infra.llm.cache.inspector")

    def get_cache_entries(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all cache entries for inspection.

        Args:
            limit: Optional limit on number of entries to return

        Returns:
            List of cache entry dictionaries
        """
        if self.settings.llm_cache_type.lower() == "sqlite":
            return self._get_sqlite_entries(limit)
        elif self.settings.llm_cache_type.lower() == "redis":
            return self._get_redis_entries(limit)
        else:
            return []

    def _get_sqlite_entries(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get entries from SQLite cache."""
        cache_path = Path(self.settings.llm_cache_sqlite_path)

        if not cache_path.exists():
            self.logger.info("cache.sqlite.not_found", path=str(cache_path))
            return []

        try:
            conn = sqlite3.connect(str(cache_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Query the cache table
            query = "SELECT * FROM full_llm_cache"
            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query)
            rows = cursor.fetchall()

            entries = []
            for row in rows:
                entries.append(
                    {
                        "prompt": (
                            row["prompt"][:100] + "..."
                            if len(row["prompt"]) > 100
                            else row["prompt"]
                        ),
                        "llm": row["llm"],
                        "response": (
                            row["response"][:200] + "..."
                            if len(row["response"]) > 200
                            else row["response"]
                        ),
                        "full_prompt": row["prompt"],
                        "full_response": row["response"],
                    }
                )

            conn.close()
            return entries

        except Exception as e:
            self.logger.error("cache.sqlite.read_error", error=str(e))
            return []

    def _get_redis_entries(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get entries from Redis cache."""
        try:
            import redis

            redis_client = redis.from_url(self.settings.redis_url)

            pattern = "langchain:*"
            keys = redis_client.keys(pattern)

            if limit:
                keys = keys[:limit]

            entries = []
            for key in keys:
                try:
                    value = redis_client.get(key)
                    if value:
                        # Attempt to decode cache value
                        cache_data = json.loads(value.decode("utf-8"))
                        entries.append(
                            {
                                "key": key.decode("utf-8"),
                                "cached_at": "unknown",  # Redis doesn't store timestamps by default
                                "data": (
                                    str(cache_data)[:200] + "..."
                                    if len(str(cache_data)) > 200
                                    else str(cache_data)
                                ),
                                "full_data": cache_data,
                            }
                        )
                except Exception as e:
                    self.logger.debug(
                        "cache.redis.entry_decode_error", key=key, error=str(e)
                    )
                    continue

            return entries

        except Exception as e:
            self.logger.error("cache.redis.read_error", error=str(e))
            return []

    def find_cached_prompts(self, search_term: str) -> List[Dict[str, Any]]:
        """
        Find cache entries containing specific terms.

        Args:
            search_term: Text to search for in prompts

        Returns:
            List of matching cache entries
        """
        all_entries = self.get_cache_entries()
        matching_entries = []

        for entry in all_entries:
            if self.settings.llm_cache_type.lower() == "sqlite":
                if search_term.lower() in entry.get("full_prompt", "").lower():
                    matching_entries.append(entry)
            elif self.settings.llm_cache_type.lower() == "redis":
                if search_term.lower() in entry.get("data", "").lower():
                    matching_entries.append(entry)

        return matching_entries

    def get_cache_summary(self) -> Dict[str, Any]:
        """Get summary statistics about the cache."""
        cache_stats = get_cache_manager().get_cache_stats()

        if not cache_stats.get("enabled"):
            return cache_stats

        entries = self.get_cache_entries()

        summary = {
            **cache_stats,
            "total_entries": len(entries),
            "sample_prompts": (
                [
                    entry.get("prompt", entry.get("data", ""))[:50] + "..."
                    for entry in entries[:5]
                ]
                if entries
                else []
            ),
        }

        if self.settings.llm_cache_type.lower() == "sqlite":
            cache_path = Path(self.settings.llm_cache_sqlite_path)
            if cache_path.exists():
                summary["last_modified"] = datetime.fromtimestamp(
                    cache_path.stat().st_mtime
                ).isoformat()

        return summary


# Convenience functions for testing workflows


def setup_test_cache() -> None:
    """Set up clean cache for testing."""
    settings = get_settings()

    if not settings.llm_cache_enabled:
        return

    # Clear existing cache
    clear_llm_cache()

    # Initialize fresh cache
    cache_manager = get_cache_manager()
    cache_manager.initialize_cache()


def populate_test_cache(test_data: List[Dict[str, str]]) -> None:
    """
    Populate cache with test data for consistent testing.

    Args:
        test_data: List of {"prompt": "...", "response": "..."} dictionaries
    """
    # This would require implementing direct cache population
    # For now, we rely on natural caching through LLM calls
    logger = get_logger("infra.llm.cache.utils")
    logger.info("cache.populate_test_data", entries=len(test_data))


def inspect_cache() -> Dict[str, Any]:
    """Quick inspection of current cache state."""
    inspector = LLMCacheInspector()
    return inspector.get_cache_summary()


def search_cache(term: str) -> List[Dict[str, Any]]:
    """Search cache for specific terms."""
    inspector = LLMCacheInspector()
    return inspector.find_cached_prompts(term)


def get_cache_entries(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent cache entries for debugging."""
    inspector = LLMCacheInspector()
    return inspector.get_cache_entries(limit)


# Export convenience functions
__all__ = [
    "LLMCacheInspector",
    "setup_test_cache",
    "populate_test_cache",
    "inspect_cache",
    "search_cache",
    "get_cache_entries",
]
