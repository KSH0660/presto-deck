"""
Test utilities for LLM caching workflows.

Provides helpers for setting up and managing cache state during testing.
"""

import pytest
from typing import Dict, List, Any
from contextlib import contextmanager

from app.infra.llm.cache_utils import setup_test_cache, inspect_cache, clear_llm_cache
from app.infra.llm.cache_manager import get_cache_manager


@contextmanager
def clean_llm_cache():
    """
    Context manager for tests that need a clean cache state.

    Usage:
        with clean_llm_cache():
            # Your test code here
            # Cache starts clean and is cleaned after test
    """
    # Clear cache before test
    clear_llm_cache()

    try:
        yield
    finally:
        # Clear cache after test to avoid side effects
        clear_llm_cache()


@contextmanager
def preserve_llm_cache():
    """
    Context manager that preserves cache state across test execution.

    Usage:
        with preserve_llm_cache():
            # Your test code here
            # Cache state is restored after test
    """
    # Note: Full restoration would require backing up actual cache data
    # For now, we just ensure cache is in a consistent state
    try:
        yield
    finally:
        cache_manager = get_cache_manager()
        cache_manager.initialize_cache()


def assert_cache_hit(prompt_fragment: str):
    """
    Assert that a prompt fragment exists in the cache (indicating a cache hit).

    Args:
        prompt_fragment: Part of the prompt to search for
    """
    from app.infra.llm.cache_utils import search_cache

    results = search_cache(prompt_fragment)
    assert (
        len(results) > 0
    ), f"Expected cache hit for prompt fragment: {prompt_fragment}"


def assert_cache_miss(prompt_fragment: str):
    """
    Assert that a prompt fragment does NOT exist in the cache.

    Args:
        prompt_fragment: Part of the prompt to search for
    """
    from app.infra.llm.cache_utils import search_cache

    results = search_cache(prompt_fragment)
    assert (
        len(results) == 0
    ), f"Expected cache miss for prompt fragment: {prompt_fragment}"


def get_cache_size() -> int:
    """Get current number of entries in cache."""
    cache_stats = inspect_cache()
    return cache_stats.get("total_entries", 0)


def wait_for_cache_entry(prompt_fragment: str, timeout: int = 10):
    """
    Wait for a cache entry to appear (useful for async operations).

    Args:
        prompt_fragment: Part of the prompt to search for
        timeout: Maximum seconds to wait
    """
    import time
    from app.infra.llm.cache_utils import search_cache

    start_time = time.time()

    while time.time() - start_time < timeout:
        results = search_cache(prompt_fragment)
        if len(results) > 0:
            return
        time.sleep(0.1)

    raise TimeoutError(f"Cache entry not found within {timeout}s: {prompt_fragment}")


# Pytest fixtures for common cache scenarios


@pytest.fixture
def clean_cache():
    """Pytest fixture providing a clean cache for each test."""
    with clean_llm_cache():
        yield


@pytest.fixture
def populated_cache():
    """
    Pytest fixture providing a cache with some test data.

    Note: This relies on natural caching through actual LLM calls
    during test setup, rather than direct cache manipulation.
    """
    setup_test_cache()

    # You would typically populate this by making actual LLM calls
    # in your test setup, which would naturally populate the cache

    yield

    # Clean up after test
    clear_llm_cache()


@pytest.fixture
def cache_inspector():
    """Pytest fixture providing cache inspection utilities."""
    from app.infra.llm.cache_utils import LLMCacheInspector

    return LLMCacheInspector()


# Test data generators for consistent testing


def generate_test_prompts() -> List[Dict[str, str]]:
    """Generate consistent test prompts for cache testing."""
    return [
        {
            "prompt": "Generate a slide about machine learning basics",
            "expected_terms": ["machine learning", "basics", "introduction"],
        },
        {
            "prompt": "Create content for data science overview",
            "expected_terms": ["data science", "overview", "statistics"],
        },
        {
            "prompt": "Write presenter notes for Python programming",
            "expected_terms": ["Python", "programming", "syntax"],
        },
    ]


def generate_cache_test_scenarios() -> List[Dict[str, Any]]:
    """Generate test scenarios for cache behavior validation."""
    return [
        {
            "name": "first_call_miss_second_hit",
            "description": "First call should miss cache, second should hit",
            "prompt": "Explain artificial intelligence fundamentals",
            "expected_cache_behavior": "miss_then_hit",
        },
        {
            "name": "different_prompts_different_cache",
            "description": "Different prompts should have separate cache entries",
            "prompts": ["Explain machine learning", "Explain deep learning"],
            "expected_cache_behavior": "separate_entries",
        },
        {
            "name": "same_prompt_same_response",
            "description": "Identical prompts should return identical cached responses",
            "prompt": "Define neural networks",
            "expected_cache_behavior": "identical_response",
        },
    ]


# Export all utilities
__all__ = [
    "clean_llm_cache",
    "preserve_llm_cache",
    "assert_cache_hit",
    "assert_cache_miss",
    "get_cache_size",
    "wait_for_cache_entry",
    "generate_test_prompts",
    "generate_cache_test_scenarios",
]
