"""Tests for LLM infrastructure layer."""

import pytest
import json
from unittest.mock import AsyncMock, Mock, patch

from app.infrastructure.llm.client import LLMClient
from app.infrastructure.llm.models import DeckPlan, SlideContent
from app.domain.exceptions import LLMException


class TestLLMClient:
    """Test cases for LLMClient."""

    @pytest.fixture
    def llm_client(self):
        """Create LLM client for testing."""
        return LLMClient()

    @pytest.fixture
    def mock_openai_response(self):
        """Mock OpenAI response."""
        mock_response = Mock()
        mock_response.content = json.dumps(
            {
                "title": "AI in Business",
                "slides": [
                    {
                        "slide_number": 1,
                        "title": "Introduction",
                        "type": "title",
                        "key_points": ["Welcome", "Overview"],
                        "content_type": "text",
                        "estimated_duration": 2,
                    },
                    {
                        "slide_number": 2,
                        "title": "AI Applications",
                        "type": "content",
                        "key_points": ["Machine Learning", "Automation"],
                        "content_type": "text",
                        "estimated_duration": 3,
                    },
                ],
                "total_slides": 2,
                "estimated_duration": 5,
                "target_audience": "Business Leaders",
            }
        )
        return mock_response

    @pytest.fixture
    def mock_slide_response(self):
        """Mock slide content response."""
        mock_response = Mock()
        mock_response.content = json.dumps(
            {
                "title": "Introduction to AI",
                "content": "AI is transforming business operations",
                "html_content": "<h1>Introduction to AI</h1><p>AI is transforming business operations</p>",
                "presenter_notes": "Welcome the audience and introduce the topic",
                "slide_number": 1,
            }
        )
        return mock_response

    def test_llm_client_initialization(self, llm_client):
        """Test LLM client initialization."""
        assert llm_client.client is None
        assert llm_client.max_retries == 3
        assert llm_client.base_delay == 1.0

    @pytest.mark.asyncio
    async def test_initialize_success(self, llm_client):
        """Test successful LLM client initialization."""
        with patch("app.infrastructure.llm.client.ChatOpenAI") as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client

            await llm_client.initialize()

            assert llm_client.client == mock_client
            mock_openai.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_missing_api_key(self, llm_client):
        """Test initialization without API key."""
        with patch("app.infrastructure.llm.client.settings") as mock_settings:
            mock_settings.openai_api_key = None

            with pytest.raises(LLMException, match="OpenAI API key not configured"):
                await llm_client.initialize()

    @pytest.mark.asyncio
    async def test_initialize_error(self, llm_client):
        """Test initialization error handling."""
        with patch("app.infrastructure.llm.client.ChatOpenAI") as mock_openai:
            mock_openai.side_effect = Exception("Connection error")

            with pytest.raises(LLMException, match="LLM client initialization failed"):
                await llm_client.initialize()

    @pytest.mark.asyncio
    async def test_generate_deck_plan_success(self, llm_client, mock_openai_response):
        """Test successful deck plan generation."""
        # Mock initialized client
        llm_client.client = Mock()

        from app.infrastructure.llm.models import SlideInfo

        # Create a proper DeckPlan object for mocking
        mock_deck_plan = DeckPlan(
            title="AI in Business",
            slides=[
                SlideInfo(
                    slide_number=1,
                    title="Introduction",
                    type="title",
                    key_points=["Welcome", "Overview"],
                    content_type="text",
                    estimated_duration=2,
                ),
                SlideInfo(
                    slide_number=2,
                    title="AI Applications",
                    type="content",
                    key_points=["Machine Learning", "Automation"],
                    content_type="text",
                    estimated_duration=3,
                ),
            ],
            total_slides=2,
            estimated_duration=5,
            target_audience="Business Leaders",
        )

        llm_client._invoke_chain_with_retry = AsyncMock(return_value=mock_deck_plan)

        with patch("app.infrastructure.llm.client.metrics") as mock_metrics:
            plan = await llm_client.generate_deck_plan(
                title="AI in Business",
                topic="How AI transforms business",
                audience="Executives",
                slide_count=2,
                style="professional",
                language="en",
            )

        assert isinstance(plan, DeckPlan)
        assert plan.title == "AI in Business"
        assert plan.total_slides == 2
        assert len(plan.slides) == 2
        assert plan.slides[0].slide_number == 1
        assert plan.slides[1].slide_number == 2
        assert plan.estimated_duration == 5
        assert plan.target_audience == "Business Leaders"

        # Verify metrics were recorded
        mock_metrics.record_llm_usage.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_deck_plan_llm_error(self, llm_client):
        """Test deck plan generation with LLM error."""
        llm_client.client = Mock()
        llm_client._invoke_chain_with_retry = AsyncMock(
            side_effect=Exception("API error")
        )

        with pytest.raises(LLMException, match="Deck plan generation failed"):
            await llm_client.generate_deck_plan(
                title="Test", topic="Test topic", slide_count=3
            )

    @pytest.mark.asyncio
    async def test_generate_slide_content_success(
        self, llm_client, mock_slide_response
    ):
        """Test successful slide content generation."""
        llm_client.client = Mock()
        # Return a SlideContent object directly from the retry wrapper
        expected = SlideContent(
            title="Introduction to AI",
            content="AI is transforming business operations",
            html_content="<h1>Introduction to AI</h1><p>AI is transforming business operations</p>",
            presenter_notes="Welcome the audience and introduce the topic",
            slide_number=1,
        )
        llm_client._invoke_chain_with_retry = AsyncMock(return_value=expected)

        slide_info = {
            "slide_number": 1,
            "title": "Introduction",
            "type": "title",
            "key_points": ["Welcome", "Overview"],
            "content_type": "text",
        }

        deck_context = {
            "title": "AI Presentation",
            "topic": "AI in Business",
            "audience": "Executives",
        }

        with patch("app.infrastructure.llm.client.metrics") as mock_metrics:
            content = await llm_client.generate_slide_content(
                slide_info=slide_info,
                deck_context=deck_context,
                slide_number=1,
                include_speaker_notes=True,
            )

        assert isinstance(content, SlideContent)
        assert content.title == "Introduction to AI"
        assert content.slide_number == 1
        assert "AI is transforming" in content.content
        assert "<h1>" in content.html_content
        assert "Welcome the audience" in content.presenter_notes

        mock_metrics.record_llm_usage.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_slide_content_without_notes(
        self, llm_client, mock_slide_response
    ):
        """Test slide content generation without speaker notes."""
        llm_client.client = Mock()
        expected = SlideContent(
            title="Slide 1",
            content="Content",
            html_content="<h1>Slide</h1>",
            presenter_notes="",
            slide_number=1,
        )
        llm_client._invoke_chain_with_retry = AsyncMock(return_value=expected)

        slide_info = {"slide_number": 1, "title": "Test"}
        deck_context = {"title": "Test Deck"}

        content = await llm_client.generate_slide_content(
            slide_info=slide_info,
            deck_context=deck_context,
            slide_number=1,
            include_speaker_notes=False,
        )

        assert isinstance(content, SlideContent)

    @pytest.mark.asyncio
    async def test_update_slide_content_success(self, llm_client, mock_slide_response):
        """Test successful slide content update."""
        llm_client.client = Mock()
        expected = SlideContent(
            title="Updated",
            content="Updated content",
            html_content="<h1>Updated</h1>",
            presenter_notes="Notes",
            slide_number=1,
        )
        llm_client._invoke_chain_with_retry = AsyncMock(return_value=expected)

        current_content = "<h1>Old Title</h1><p>Old content</p>"
        update_prompt = "Make it more engaging"
        slide_context = {"slide_number": 1, "deck_title": "Test Deck"}

        with patch("app.infrastructure.llm.client.metrics") as mock_metrics:
            updated_content = await llm_client.update_slide_content(
                current_content=current_content,
                update_prompt=update_prompt,
                slide_context=slide_context,
            )

        assert isinstance(updated_content, SlideContent)
        assert updated_content.title == "Updated"
        mock_metrics.record_llm_usage.assert_called_once()

    @pytest.mark.asyncio
    async def test_invoke_chain_with_retry_success(self, llm_client):
        """Test successful chain invoke with retry logic."""
        chain = Mock()
        chain.ainvoke = AsyncMock(return_value={"ok": True})
        result = await llm_client._invoke_chain_with_retry(chain, {"x": 1})
        assert result == {"ok": True}
        chain.ainvoke.assert_called_once_with({"x": 1})

    @pytest.mark.asyncio
    async def test_invoke_chain_with_retry_failure_then_success(self, llm_client):
        """Test chain invoke with retry after initial failure."""
        chain = Mock()
        chain.ainvoke = AsyncMock(side_effect=[Exception("Temporary"), {"ok": True}])
        llm_client.max_retries = 2
        with patch("asyncio.sleep"):
            result = await llm_client._invoke_chain_with_retry(chain, {"x": 1})
        assert result == {"ok": True}
        assert chain.ainvoke.call_count == 2

    @pytest.mark.asyncio
    async def test_invoke_chain_with_retry_max_failures(self, llm_client):
        """Test chain invoke exceeding max retries."""
        chain = Mock()
        chain.ainvoke = AsyncMock(side_effect=Exception("Persistent"))
        llm_client.max_retries = 2
        with patch("asyncio.sleep"):
            with pytest.raises(LLMException):
                await llm_client._invoke_chain_with_retry(chain, {"x": 1})
        assert chain.ainvoke.call_count == 2

    @pytest.mark.asyncio
    async def test_invoke_chain_with_retry_propagates_exceptions(self, llm_client):
        """Test that missing variables or chain errors bubble through retry and wrap."""
        chain = Mock()
        chain.ainvoke = AsyncMock(side_effect=Exception("bad input"))
        llm_client.max_retries = 1
        with pytest.raises(LLMException):
            await llm_client._invoke_chain_with_retry(chain, {"x": 1})

    def test_prompts_have_expected_placeholders_deck_plan(self):
        """Ensure deck plan prompt variables align with client inputs."""
        from app.infrastructure.llm.prompts import DECK_PLAN_PROMPT

        vars_ = set(DECK_PLAN_PROMPT.input_variables)
        assert vars_ == {
            "title",
            "topic",
            "audience",
            "slide_count",
            "style",
            "language",
        }

    def test_prompts_have_expected_placeholders_slide_content(self):
        """Ensure slide content prompt variables align with client inputs."""
        from app.infrastructure.llm.prompts import SLIDE_CONTENT_PROMPT

        vars_ = set(SLIDE_CONTENT_PROMPT.input_variables)
        assert vars_ == {
            "deck_title",
            "deck_topic",
            "deck_audience",
            "slide_number",
            "slide_title",
            "slide_type",
            "key_points",
            "content_type",
            "notes_detail",
        }

    def test_prompts_have_expected_placeholders_slide_update(self):
        """Ensure slide update prompt variables align with client inputs."""
        from app.infrastructure.llm.prompts import SLIDE_UPDATE_PROMPT

        vars_ = set(SLIDE_UPDATE_PROMPT.input_variables)
        assert vars_ == {"current_content", "update_prompt", "slide_context"}

    @pytest.mark.asyncio
    async def test_generate_deck_plan_passes_expected_inputs(self, llm_client):
        """Verify input mapping for deck plan generation."""
        llm_client.client = Mock()
        llm_client.client.with_structured_output = Mock(return_value=Mock())
        expected = DeckPlan(
            title="T",
            slides=[],
            total_slides=0,
            estimated_duration=0,
            target_audience="A",
        )
        with patch.object(
            llm_client, "_invoke_chain_with_retry", return_value=expected
        ) as spy:
            await llm_client.generate_deck_plan(
                title="T",
                topic="Top",
                audience="Aud",
                slide_count=3,
                style="pro",
                language="en",
            )
        args, kwargs = spy.call_args
        input_dict = args[1]
        assert set(input_dict.keys()) == {
            "title",
            "topic",
            "audience",
            "slide_count",
            "style",
            "language",
        }

    @pytest.mark.asyncio
    async def test_generate_slide_content_passes_expected_inputs(self, llm_client):
        """Verify input mapping for slide content generation."""
        llm_client.client = Mock()
        llm_client.client.with_structured_output = Mock(return_value=Mock())
        expected = SlideContent(
            title="t",
            content="c",
            html_content="<h1>t</h1>",
            presenter_notes="n",
            slide_number=1,
        )
        with patch.object(
            llm_client, "_invoke_chain_with_retry", return_value=expected
        ) as spy:
            await llm_client.generate_slide_content(
                slide_info={
                    "title": "Intro",
                    "type": "title",
                    "key_points": ["a", "b"],
                    "content_type": "text",
                },
                deck_context={"title": "Deck", "topic": "Topic", "audience": "People"},
                slide_number=1,
                include_speaker_notes=True,
            )
        args, kwargs = spy.call_args
        input_dict = args[1]
        assert set(input_dict.keys()) == {
            "deck_title",
            "deck_topic",
            "deck_audience",
            "slide_number",
            "slide_title",
            "slide_type",
            "key_points",
            "content_type",
            "notes_detail",
        }
        assert input_dict["notes_detail"] == "detailed"

    @pytest.mark.asyncio
    async def test_update_slide_content_passes_expected_inputs(self, llm_client):
        """Verify input mapping for slide update generation."""
        llm_client.client = Mock()
        llm_client.client.with_structured_output = Mock(return_value=Mock())
        expected = SlideContent(
            title="t2",
            content="c2",
            html_content="<h1>u</h1>",
            presenter_notes="n2",
            slide_number=1,
        )
        with patch.object(
            llm_client, "_invoke_chain_with_retry", return_value=expected
        ) as spy:
            await llm_client.update_slide_content(
                current_content="<h1>Old</h1>",
                update_prompt="Make it better",
                slide_context={"x": 1},
            )
        args, kwargs = spy.call_args
        input_dict = args[1]
        assert set(input_dict.keys()) == {
            "current_content",
            "update_prompt",
            "slide_context",
        }

    # Prompt string construction unit tests have been replaced by placeholder
    # assertions and input mapping checks above, which align with structured outputs.

    @pytest.mark.asyncio
    async def test_close_client(self, llm_client):
        """Test client closing."""
        # Should not raise any exceptions
        await llm_client.close()


class TestDeckPlan:
    """Test cases for DeckPlan model."""

    def test_deck_plan_creation(self):
        """Test DeckPlan creation."""
        from app.infrastructure.llm.models import SlideInfo

        slides = [
            SlideInfo(
                slide_number=1,
                title="Introduction",
                type="title",
                key_points=["Intro"],
                content_type="text",
                estimated_duration=2,
            ),
            SlideInfo(
                slide_number=2,
                title="Content",
                type="content",
                key_points=["Point"],
                content_type="text",
                estimated_duration=3,
            ),
        ]

        plan = DeckPlan(
            title="Test Deck",
            slides=slides,
            total_slides=2,
            estimated_duration=5,
            target_audience="Developers",
        )

        assert plan.title == "Test Deck"
        assert plan.slides == slides
        assert plan.total_slides == 2
        assert plan.estimated_duration == 5
        assert plan.target_audience == "Developers"

    def test_deck_plan_dict(self):
        """Test DeckPlan dict conversion."""
        plan = DeckPlan(
            title="Test Deck",
            slides=[],
            total_slides=0,
            estimated_duration=0,
            target_audience="Test",
        )

        plan_dict = plan.model_dump()

        assert plan_dict["title"] == "Test Deck"
        assert "slides" in plan_dict
        assert "total_slides" in plan_dict
        assert "estimated_duration" in plan_dict
        assert "target_audience" in plan_dict


class TestSlideContent:
    """Test cases for SlideContent model."""

    def test_slide_content_creation(self):
        """Test SlideContent creation."""
        content = SlideContent(
            title="Test Slide",
            content="Test content",
            html_content="<h1>Test Slide</h1>",
            presenter_notes="Test notes",
            slide_number=1,
        )

        assert content.title == "Test Slide"
        assert content.content == "Test content"
        assert content.html_content == "<h1>Test Slide</h1>"
        assert content.presenter_notes == "Test notes"
        assert content.slide_number == 1

    def test_slide_content_dict(self):
        """Test SlideContent dict conversion."""
        content = SlideContent(
            title="Test",
            content="Test",
            html_content="<h1>Test</h1>",
            presenter_notes="Notes",
            slide_number=1,
        )

        content_dict = content.model_dump()

        assert content_dict["title"] == "Test"
        assert "content" in content_dict
        assert "html_content" in content_dict
        assert "presenter_notes" in content_dict
        assert "slide_number" in content_dict
