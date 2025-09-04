"""
Integration tests for LLM client with caching validation.

These tests verify actual LLM communication and caching behavior with external systems.
"""

import pytest
from unittest.mock import patch

from app.infra.llm.langchain_client import LangChainClient
from app.infra.llm.cache_manager import initialize_llm_cache
from app.infra.llm.cache_utils import get_cache_entries, search_cache, inspect_cache
from app.infra.config.settings import get_settings
from langchain_core.messages import HumanMessage
from tests.utils.cache_helpers import (
    assert_cache_hit,
    get_cache_size,
)


@pytest.mark.integration
@pytest.mark.cache
class TestLLMCacheIntegration:
    """Test LLM caching behavior in integration scenarios."""

    @pytest.fixture
    def llm_client(self, enable_llm_cache):
        """Create LLM client with caching enabled."""
        settings = get_settings()
        return LangChainClient(
            model_name=settings.openai_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

    async def test_cache_initialization(self, clean_cache):
        """Test that cache initializes correctly."""
        # Cache should start empty
        initial_stats = inspect_cache()
        assert initial_stats["enabled"] is True
        assert initial_stats["total_entries"] == 0

        # Initialize cache
        initialize_llm_cache()

        stats = inspect_cache()
        assert stats["enabled"] is True
        assert stats["type"] == "sqlite"

    async def test_cache_miss_then_hit_pattern(self, llm_client, clean_cache):
        """Test that first call misses cache, second call hits cache."""
        test_prompt = "What is machine learning? Keep it brief."
        messages = [HumanMessage(content=test_prompt)]

        # First call should miss cache
        initial_cache_size = get_cache_size()

        with patch("langchain_openai.ChatOpenAI.ainvoke") as mock_llm:
            mock_response = type(
                "MockResponse", (), {"content": "Machine learning is AI subset"}
            )()
            mock_llm.return_value = mock_response

            response1 = await llm_client.invoke_text(messages)
            assert response1 == "Machine learning is AI subset"

            # Cache should now have one entry
            assert get_cache_size() == initial_cache_size + 1
            assert_cache_hit(test_prompt[:20])  # Check partial prompt

            # Second identical call should hit cache (no additional LLM call)
            mock_llm.reset_mock()
            response2 = await llm_client.invoke_text(messages)

            # Should return same response
            assert response2 == response1
            # Mock should not be called again (cache hit)
            mock_llm.assert_not_called()
            # Cache size should remain the same
            assert get_cache_size() == initial_cache_size + 1

    async def test_different_prompts_separate_cache_entries(
        self, llm_client, clean_cache
    ):
        """Test that different prompts create separate cache entries."""
        prompts = [
            "Explain supervised learning",
            "Explain unsupervised learning",
            "Explain reinforcement learning",
        ]

        with patch("langchain_openai.ChatOpenAI.ainvoke") as mock_llm:
            mock_responses = [
                type("MockResponse", (), {"content": f"Response for prompt {i}"})()
                for i in range(len(prompts))
            ]
            mock_llm.side_effect = mock_responses

            # Make calls with different prompts
            responses = []
            for prompt in prompts:
                messages = [HumanMessage(content=prompt)]
                response = await llm_client.invoke_text(messages)
                responses.append(response)

            # Should have separate cache entries
            assert get_cache_size() == len(prompts)

            # Each prompt should be in cache
            for prompt in prompts:
                assert_cache_hit(prompt[:15])

            # Responses should be different
            assert len(set(responses)) == len(responses)

    async def test_cache_with_structured_output(self, llm_client, clean_cache):
        """Test caching behavior with structured output."""
        from pydantic import BaseModel

        class TestResponse(BaseModel):
            title: str
            description: str

        messages = [HumanMessage(content="Create a test response")]

        with patch(
            "langchain_openai.ChatOpenAI.with_structured_output"
        ) as mock_structured:
            mock_llm_instance = mock_structured.return_value
            mock_response = TestResponse(title="Test", description="A test response")
            mock_llm_instance.ainvoke.return_value = mock_response

            # First call
            response1 = await llm_client.invoke_structured(messages, TestResponse)
            assert response1.title == "Test"

            # Second call should hit cache
            mock_llm_instance.ainvoke.reset_mock()
            response2 = await llm_client.invoke_structured(messages, TestResponse)

            assert response2.title == response1.title
            # Should not make additional LLM call
            mock_llm_instance.ainvoke.assert_not_called()

    async def test_cache_search_functionality(self, llm_client, clean_cache):
        """Test cache search and inspection utilities."""
        test_prompts = [
            "Machine learning basics",
            "Deep learning concepts",
            "Natural language processing",
        ]

        with patch("langchain_openai.ChatOpenAI.ainvoke") as mock_llm:
            mock_llm.return_value = type(
                "MockResponse", (), {"content": "Test response"}
            )()

            # Populate cache with test data
            for prompt in test_prompts:
                messages = [HumanMessage(content=prompt)]
                await llm_client.invoke_text(messages)

            # Test search functionality
            ml_results = search_cache("machine learning")
            assert len(ml_results) > 0

            dl_results = search_cache("deep learning")
            assert len(dl_results) > 0

            # Test cache inspection
            all_entries = get_cache_entries(limit=10)
            assert len(all_entries) == len(test_prompts)

    async def test_cache_persistence_across_sessions(self, clean_cache):
        """Test that cache persists across different client instances."""
        settings = get_settings()
        test_prompt = "Persistent cache test"
        messages = [HumanMessage(content=test_prompt)]

        # First client instance
        with patch("langchain_openai.ChatOpenAI.ainvoke") as mock_llm1:
            mock_llm1.return_value = type(
                "MockResponse", (), {"content": "Cached response"}
            )()

            client1 = LangChainClient(
                model_name=settings.openai_model,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )

            response1 = await client1.invoke_text(messages)
            assert response1 == "Cached response"
            assert_cache_hit(test_prompt[:15])

        # Second client instance (simulating new session)
        with patch("langchain_openai.ChatOpenAI.ainvoke") as mock_llm2:
            client2 = LangChainClient(
                model_name=settings.openai_model,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )

            # Should hit cache, not call LLM
            response2 = await client2.invoke_text(messages)
            assert response2 == response1
            mock_llm2.assert_not_called()  # Should not make new LLM call


@pytest.mark.integration
@pytest.mark.llm
@pytest.mark.external
class TestLLMRealAPIIntegration:
    """Test integration with real LLM API (requires valid API key)."""

    @pytest.fixture
    def real_llm_client(self, check_llm_api_available):
        """Create LLM client for real API testing."""
        if not check_llm_api_available:
            pytest.skip("Real LLM API not available (no API key)")

        # Temporarily enable real API key for testing
        import os

        original_key = os.environ.get("OPENAI_API_KEY")
        if original_key and original_key != "dummy-key-for-test":
            os.environ["OPENAI_API_KEY"] = original_key

        return LangChainClient(
            model_name="gpt-4o-mini",  # Use cheaper model for testing
            temperature=0.1,  # Low temperature for consistency
            max_tokens=100,  # Limit tokens to reduce cost
        )

    @pytest.mark.slow
    async def test_real_llm_response_caching(self, real_llm_client, clean_cache):
        """Test actual LLM API call with caching."""
        test_prompt = "What is 2+2? Answer with just the number."
        messages = [HumanMessage(content=test_prompt)]

        # First call - should hit real API
        response1 = await real_llm_client.invoke_text(messages)
        assert "4" in response1  # Should contain the answer
        assert_cache_hit(test_prompt[:10])

        # Second call - should hit cache
        response2 = await real_llm_client.invoke_text(messages)
        assert response2 == response1  # Should be identical from cache

        # Verify cache statistics
        stats = inspect_cache()
        assert stats["total_entries"] >= 1

    @pytest.mark.slow
    async def test_real_llm_structured_response(self, real_llm_client, clean_cache):
        """Test real LLM API with structured output."""
        from pydantic import BaseModel

        class MathAnswer(BaseModel):
            question: str
            answer: int
            explanation: str

        messages = [HumanMessage(content="What is 5+3? Provide a structured response.")]

        # Test structured output with real API
        response = await real_llm_client.invoke_structured(messages, MathAnswer)
        assert isinstance(response, MathAnswer)
        assert response.answer == 8
        assert (
            "5+3" in response.question.lower() or "5 + 3" in response.question.lower()
        )

    @pytest.mark.slow
    async def test_cache_behavior_with_temperature_variations(self, clean_cache):
        """Test that different temperatures create separate cache entries."""
        from app.infra.config.settings import get_settings

        if not get_settings().openai_api_key != "dummy-key-for-test":
            pytest.skip("Real LLM API not available")

        prompt = "Generate a creative story starter"
        messages = [HumanMessage(content=prompt)]

        # Create clients with different temperatures
        client_low_temp = LangChainClient(
            model_name="gpt-4o-mini", temperature=0.1, max_tokens=50
        )
        client_high_temp = LangChainClient(
            model_name="gpt-4o-mini", temperature=0.9, max_tokens=50
        )

        # Both should call API (different temperatures = different cache keys)
        await client_low_temp.invoke_text(messages)
        await client_high_temp.invoke_text(messages)

        # Responses might be different due to temperature
        # But both should be cached separately
        assert get_cache_size() >= 2
