"""
Unit tests for use cases with mocked dependencies.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4
from datetime import datetime, timezone

from app.application.use_cases.create_deck_plan import CreateDeckPlanUseCase
from app.application.use_cases.select_template import SelectTemplateUseCase
from app.application.use_cases.write_slide_content import WriteSlideContentUseCase
from app.api.schemas import DeckStatus
from app.domain.entities.deck import Deck
from app.domain.entities.slide import Slide


class TestCreateDeckPlanUseCase:
    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for use case."""
        return {
            "uow": Mock(),
            "deck_repo": Mock(),
            "event_repo": Mock(),
            "arq_client": AsyncMock(),
            "ws_broadcaster": AsyncMock(),
        }

    @pytest.fixture
    def use_case(self, mock_dependencies):
        """Create use case with mocked dependencies."""
        return CreateDeckPlanUseCase(**mock_dependencies)

    @pytest.mark.asyncio
    async def test_execute_success(self, use_case, mock_dependencies):
        """Test successful deck plan creation."""
        # Arrange
        user_id = uuid4()
        prompt = "Create a presentation about machine learning"
        style_preferences = {"theme": "professional"}

        mock_dependencies["uow"].__aenter__ = AsyncMock(
            return_value=mock_dependencies["uow"]
        )
        mock_dependencies["uow"].__aexit__ = AsyncMock(return_value=None)
        mock_dependencies["uow"].commit = AsyncMock()
        mock_dependencies["deck_repo"].create = AsyncMock()
        mock_dependencies["event_repo"].store_event = AsyncMock()
        mock_dependencies["arq_client"].enqueue = AsyncMock(return_value="job-123")

        # Act
        result = await use_case.execute(user_id, prompt, style_preferences)

        # Assert
        assert result["status"] == DeckStatus.PENDING.value
        assert result["message"] == "Deck creation initiated"
        assert "deck_id" in result

        mock_dependencies["deck_repo"].create.assert_called_once()
        mock_dependencies["event_repo"].store_event.assert_called_once()
        mock_dependencies["uow"].commit.assert_called_once()
        mock_dependencies["arq_client"].enqueue.assert_called_once_with(
            "generate_deck_plan",
            deck_id=result["deck_id"],
            user_id=str(user_id),
            prompt=prompt,
            style_preferences=style_preferences,
        )

    @pytest.mark.asyncio
    async def test_execute_invalid_prompt_raises_error(self, use_case):
        """Test invalid prompt raises validation error."""
        user_id = uuid4()
        invalid_prompt = "short"  # Too short

        with pytest.raises(ValueError, match="at least 10 characters"):
            await use_case.execute(user_id, invalid_prompt)

    @pytest.mark.asyncio
    async def test_execute_invalid_style_preferences_raises_error(self, use_case):
        """Test invalid style preferences raise validation error."""
        user_id = uuid4()
        prompt = "Valid prompt that is long enough"
        invalid_style = {"invalid_key": "value"}

        with pytest.raises(ValueError, match="Invalid style preference keys"):
            await use_case.execute(user_id, prompt, invalid_style)


class TestSelectTemplateUseCase:
    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for use case."""
        return {
            "uow": Mock(),
            "deck_repo": Mock(),
            "slide_repo": Mock(),
            "event_repo": Mock(),
            "arq_client": AsyncMock(),
            "ws_broadcaster": AsyncMock(),
            "llm_client": AsyncMock(),
            "template_catalog": Mock(),
        }

    @pytest.fixture
    def use_case(self, mock_dependencies):
        """Create use case with mocked dependencies."""
        return SelectTemplateUseCase(**mock_dependencies)

    @pytest.mark.asyncio
    async def test_execute_success(self, use_case, mock_dependencies):
        """Test successful template selection."""
        # Arrange
        deck_id = uuid4()
        user_id = uuid4()
        deck_plan = {
            "title": "ML Presentation",
            "slides": [
                {"title": "Introduction", "content": "Overview of ML"},
                {"title": "Algorithms", "content": "Different ML algorithms"},
            ],
        }

        mock_deck = Deck(
            id=deck_id,
            user_id=user_id,
            prompt="test",
            status=DeckStatus.PLANNING,
            style_preferences={},
            created_at=datetime.now(timezone.utc),
        )

        mock_dependencies["deck_repo"].get_by_id = AsyncMock(return_value=mock_deck)
        mock_dependencies["deck_repo"].update = AsyncMock()

        # Mock slide creation with ID assignment
        async def mock_create_slide(slide):
            slide.id = uuid4()  # Assign ID like a real repository would
            return slide

        mock_dependencies["slide_repo"].create = AsyncMock(
            side_effect=mock_create_slide
        )
        mock_dependencies["event_repo"].store_event = AsyncMock()
        # Mock structured output response
        from app.domain.value_objects.template_selection import (
            DeckTemplateSelections,
            SlideTemplateAssignment,
        )

        mock_template_selections = DeckTemplateSelections(
            deck_theme="professional",
            slide_assignments=[
                SlideTemplateAssignment(
                    slide_order=1,
                    slide_title="Introduction",
                    primary_template="intro_slide.html",
                    alternative_templates=["content_slide.html"],
                    content_adaptation_notes="Professional introduction style",
                ),
                SlideTemplateAssignment(
                    slide_order=2,
                    slide_title="Algorithms",
                    primary_template="content_slide.html",
                    alternative_templates=["bullet_slide.html"],
                    content_adaptation_notes="Technical content with examples",
                ),
            ],
            template_usage_summary={"intro_slide.html": 1, "content_slide.html": 1},
        )
        mock_dependencies["llm_client"].generate_structured = AsyncMock(
            return_value=mock_template_selections
        )

        # Mock template catalog
        mock_dependencies["template_catalog"].get_catalog_for_llm = Mock(
            return_value={
                "intro_slide.html": "Introduction slide template",
                "content_slide.html": "Content slide template",
            }
        )
        mock_dependencies["arq_client"].enqueue = AsyncMock(return_value="job-123")

        mock_dependencies["uow"].__aenter__ = AsyncMock(
            return_value=mock_dependencies["uow"]
        )
        mock_dependencies["uow"].__aexit__ = AsyncMock(return_value=None)
        mock_dependencies["uow"].commit = AsyncMock()

        # Act
        result = await use_case.execute(deck_id, deck_plan)

        # Assert
        assert result["deck_id"] == str(deck_id)
        assert result["slide_count"] == 2
        assert result["status"] == DeckStatus.GENERATING.value
        assert "template_selections" in result

        mock_dependencies["deck_repo"].update.assert_called_once()
        assert (
            mock_dependencies["slide_repo"].create.call_count == 2
        )  # Two slides created
        assert (
            mock_dependencies["event_repo"].store_event.call_count == 2
        )  # Two events stored

    @pytest.mark.asyncio
    async def test_execute_deck_not_found_raises_error(
        self, use_case, mock_dependencies
    ):
        """Test deck not found raises error."""
        deck_id = uuid4()
        deck_plan = {"slides": [{"title": "Test", "content": "Test"}]}

        mock_dependencies["deck_repo"].get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Deck .* not found"):
            await use_case.execute(deck_id, deck_plan)

    @pytest.mark.asyncio
    async def test_execute_deck_wrong_status_raises_error(
        self, use_case, mock_dependencies
    ):
        """Test deck in wrong status raises error."""
        deck_id = uuid4()
        deck_plan = {"slides": [{"title": "Test", "content": "Test"}]}

        mock_deck = Deck(
            id=deck_id,
            user_id=uuid4(),
            prompt="test",
            status=DeckStatus.PENDING,  # Should be PLANNING
            style_preferences={},
            created_at=datetime.now(timezone.utc),
        )

        mock_dependencies["deck_repo"].get_by_id = AsyncMock(return_value=mock_deck)

        with pytest.raises(ValueError, match="must be in PLANNING status"):
            await use_case.execute(deck_id, deck_plan)


class TestWriteSlideContentUseCase:
    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for use case."""
        return {
            "uow": Mock(),
            "deck_repo": Mock(),
            "slide_repo": Mock(),
            "event_repo": Mock(),
            "ws_broadcaster": AsyncMock(),
            "llm_client": AsyncMock(),
            "template_catalog": Mock(),
        }

    @pytest.fixture
    def use_case(self, mock_dependencies):
        """Create use case with mocked dependencies."""
        return WriteSlideContentUseCase(**mock_dependencies)

    @pytest.mark.asyncio
    async def test_execute_success(self, use_case, mock_dependencies):
        """Test successful slide content generation."""
        # Arrange
        deck_id = uuid4()
        slide_id = uuid4()
        content_outline = "Introduction to machine learning concepts"

        mock_slide = Slide(
            id=slide_id,
            deck_id=deck_id,
            order=1,
            title="Introduction",
            content_outline=content_outline,
            html_content=None,
            presenter_notes="Welcome slide",
            template_filename="professional_slide.html",
            created_at=datetime.now(timezone.utc),
        )

        mock_dependencies["slide_repo"].get_by_id = AsyncMock(return_value=mock_slide)
        mock_dependencies["slide_repo"].update = AsyncMock()
        mock_dependencies["slide_repo"].count_incomplete_slides = AsyncMock(
            return_value=2
        )

        # Mock template catalog for WriteSlideContent test
        mock_dependencies["template_catalog"].get_template_content = Mock(
            return_value="<div class='slide-template'>Template content here</div>"
        )
        mock_dependencies["event_repo"].store_event = AsyncMock()
        mock_dependencies["llm_client"].generate_text = AsyncMock(
            return_value="<h1>Introduction</h1><p>ML content here</p>"
        )

        mock_dependencies["uow"].__aenter__ = AsyncMock(
            return_value=mock_dependencies["uow"]
        )
        mock_dependencies["uow"].__aexit__ = AsyncMock(return_value=None)
        mock_dependencies["uow"].commit = AsyncMock()

        # Act
        result = await use_case.execute(
            deck_id=deck_id,
            slide_id=slide_id,
            slide_order=1,
            content_outline=content_outline,
            primary_template="professional_slide.html",
            alternative_templates=["content_slide.html"],
            adaptation_notes="Professional style presentation",
        )

        # Assert
        assert result["status"] == "completed"
        assert result["slide_order"] == 1
        assert result["deck_completed"] is False  # Still 2 incomplete slides

        mock_dependencies["slide_repo"].update.assert_called_once()
        mock_dependencies["event_repo"].store_event.assert_called_once()
        mock_dependencies["uow"].commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_slide_not_found_raises_error(
        self, use_case, mock_dependencies
    ):
        """Test slide not found raises error."""
        deck_id = uuid4()
        slide_id = uuid4()

        mock_dependencies["slide_repo"].get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Slide .* not found"):
            await use_case.execute(
                deck_id=deck_id,
                slide_id=slide_id,
                slide_order=1,
                content_outline="test content",
                primary_template="professional_slide.html",
            )

    @pytest.mark.asyncio
    async def test_execute_slide_wrong_deck_raises_error(
        self, use_case, mock_dependencies
    ):
        """Test slide belonging to wrong deck raises error."""
        deck_id = uuid4()
        slide_id = uuid4()
        other_deck_id = uuid4()

        mock_slide = Slide(
            id=slide_id,
            deck_id=other_deck_id,  # Different deck ID
            order=1,
            title="Test",
            content_outline="test",
            html_content=None,
            presenter_notes="",
            template_filename="minimal_slide.html",
            created_at=datetime.now(timezone.utc),
        )

        mock_dependencies["slide_repo"].get_by_id = AsyncMock(return_value=mock_slide)

        with pytest.raises(ValueError, match="does not belong to deck"):
            await use_case.execute(
                deck_id=deck_id,
                slide_id=slide_id,
                slide_order=1,
                content_outline="test content",
                primary_template="professional_slide.html",
            )

    @pytest.mark.asyncio
    async def test_execute_slide_already_has_content_raises_error(
        self, use_case, mock_dependencies
    ):
        """Test slide with existing content raises error."""
        deck_id = uuid4()
        slide_id = uuid4()

        mock_slide = Slide(
            id=slide_id,
            deck_id=deck_id,
            order=1,
            title="Test",
            content_outline="test",
            html_content="<h1>Existing content</h1>",  # Already has content
            presenter_notes="",
            template_filename="minimal_slide.html",
            created_at=datetime.now(timezone.utc),
        )

        mock_dependencies["slide_repo"].get_by_id = AsyncMock(return_value=mock_slide)

        with pytest.raises(ValueError, match="already has content"):
            await use_case.execute(
                deck_id=deck_id,
                slide_id=slide_id,
                slide_order=1,
                content_outline="test content",
                primary_template="professional_slide.html",
            )
