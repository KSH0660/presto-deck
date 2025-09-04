"""
LLM Cache Management for development and testing workflows.

Provides centralized caching configuration for LangChain to reduce API costs
and improve test consistency across environments.
"""

from typing import Optional
from pathlib import Path

from langchain_community.cache import SQLiteCache
from langchain_community.cache import RedisCache
from langchain.globals import set_llm_cache
import redis

from app.infra.config.settings import get_settings
from app.infra.config.logging_config import get_logger


class LLMCacheManager:
    """Manages LLM caching configuration across environments."""

    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger("infra.llm.cache")
        self._cache_initialized = False

    def initialize_cache(self) -> None:
        """Initialize appropriate cache based on settings."""
        if not self.settings.llm_cache_enabled:
            self.logger.info("llm_cache.disabled")
            return

        if self._cache_initialized:
            self.logger.debug("llm_cache.already_initialized")
            return

        cache_type = self.settings.llm_cache_type.lower()

        try:
            if cache_type == "sqlite":
                self._setup_sqlite_cache()
            elif cache_type == "redis":
                self._setup_redis_cache()
            elif cache_type == "memory":
                self._setup_memory_cache()
            else:
                self.logger.warning(
                    "llm_cache.unknown_type", cache_type=cache_type, fallback="sqlite"
                )
                self._setup_sqlite_cache()

            self._cache_initialized = True
            self.logger.info("llm_cache.initialized", cache_type=cache_type)

        except Exception as e:
            self.logger.error(
                "llm_cache.initialization_failed", cache_type=cache_type, error=str(e)
            )
            # Don't raise - allow application to continue without caching

    def _setup_sqlite_cache(self) -> None:
        """Set up SQLite-based cache for development and testing."""
        cache_path = Path(self.settings.llm_cache_sqlite_path)

        # Ensure cache directory exists
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        # Create SQLite cache
        sqlite_cache = SQLiteCache(database_path=str(cache_path))
        set_llm_cache(sqlite_cache)

        self.logger.info("llm_cache.sqlite.ready", path=str(cache_path))

    def _setup_redis_cache(self) -> None:
        """Set up Redis-based cache for production environments."""
        try:
            # Use existing Redis connection from settings
            redis_client = redis.from_url(self.settings.redis_url)

            # Test connection
            redis_client.ping()

            # Create Redis cache with TTL
            redis_cache = RedisCache(
                redis_=redis_client, ttl=self.settings.llm_cache_ttl
            )
            set_llm_cache(redis_cache)

            self.logger.info("llm_cache.redis.ready", url=self.settings.redis_url)

        except Exception as e:
            self.logger.warning("llm_cache.redis.fallback_to_sqlite", error=str(e))
            self._setup_sqlite_cache()

    def _setup_memory_cache(self) -> None:
        """Set up in-memory cache (not persistent)."""
        from langchain.cache import InMemoryCache

        memory_cache = InMemoryCache()
        set_llm_cache(memory_cache)

        self.logger.info("llm_cache.memory.ready")

    def clear_cache(self) -> None:
        """Clear the current cache (useful for testing)."""
        if not self.settings.llm_cache_enabled:
            return

        try:
            cache_type = self.settings.llm_cache_type.lower()

            if cache_type == "sqlite":
                self._clear_sqlite_cache()
            elif cache_type == "redis":
                self._clear_redis_cache()
            elif cache_type == "memory":
                # Memory cache is cleared by reinitializing
                self._setup_memory_cache()

            self.logger.info("llm_cache.cleared", cache_type=cache_type)

        except Exception as e:
            self.logger.error("llm_cache.clear_failed", error=str(e))

    def _clear_sqlite_cache(self) -> None:
        """Clear SQLite cache by removing the database file."""
        cache_path = Path(self.settings.llm_cache_sqlite_path)
        if cache_path.exists():
            cache_path.unlink()
            self.logger.info("llm_cache.sqlite.cleared", path=str(cache_path))

        # Reinitialize
        self._cache_initialized = False
        self._setup_sqlite_cache()

    def _clear_redis_cache(self) -> None:
        """Clear Redis cache entries."""
        try:
            redis_client = redis.from_url(self.settings.redis_url)

            # Get all LangChain cache keys (they typically start with specific prefix)
            pattern = "langchain:*"
            cache_keys = redis_client.keys(pattern)

            if cache_keys:
                redis_client.delete(*cache_keys)
                self.logger.info(
                    "llm_cache.redis.cleared", keys_deleted=len(cache_keys)
                )
            else:
                self.logger.info("llm_cache.redis.no_keys_to_clear")

        except Exception as e:
            self.logger.error("llm_cache.redis.clear_failed", error=str(e))

    def get_cache_stats(self) -> dict:
        """Get cache statistics (if available)."""
        if not self.settings.llm_cache_enabled or not self._cache_initialized:
            return {"enabled": False}

        stats = {
            "enabled": True,
            "type": self.settings.llm_cache_type,
            "ttl": self.settings.llm_cache_ttl,
        }

        cache_type = self.settings.llm_cache_type.lower()

        try:
            if cache_type == "sqlite":
                stats.update(self._get_sqlite_stats())
            elif cache_type == "redis":
                stats.update(self._get_redis_stats())
        except Exception as e:
            stats["error"] = str(e)

        return stats

    def _get_sqlite_stats(self) -> dict:
        """Get SQLite cache statistics."""
        cache_path = Path(self.settings.llm_cache_sqlite_path)

        return {
            "path": str(cache_path),
            "exists": cache_path.exists(),
            "size_bytes": cache_path.stat().st_size if cache_path.exists() else 0,
        }

    def _get_redis_stats(self) -> dict:
        """Get Redis cache statistics."""
        try:
            redis_client = redis.from_url(self.settings.redis_url)
            pattern = "langchain:*"
            cache_keys = redis_client.keys(pattern)

            return {
                "url": self.settings.redis_url,
                "cache_keys_count": len(cache_keys),
                "redis_info": redis_client.info("memory"),
            }
        except Exception as e:
            return {"error": str(e)}


# Global cache manager instance
_cache_manager: Optional[LLMCacheManager] = None


def get_cache_manager() -> LLMCacheManager:
    """Get the global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = LLMCacheManager()
    return _cache_manager


def initialize_llm_cache() -> None:
    """Initialize LLM cache - call this at application startup."""
    cache_manager = get_cache_manager()
    cache_manager.initialize_cache()


def clear_llm_cache() -> None:
    """Clear LLM cache - useful for testing and debugging."""
    cache_manager = get_cache_manager()
    cache_manager.clear_cache()


def get_llm_cache_stats() -> dict:
    """Get LLM cache statistics."""
    cache_manager = get_cache_manager()
    return cache_manager.get_cache_stats()
