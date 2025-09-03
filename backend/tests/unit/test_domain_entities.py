"""
Unit tests for domain entities.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from app.domain_core.entities.deck import Deck
from app.domain_core.entities.slide import Slide
from app.api.schemas import DeckStatus


class TestDeckEntity:
    def test_deck_creation(self):
        """Test deck entity creation."""
        deck_id = uuid4()
        user_id = uuid4()
        now = datetime.now(timezone.utc)

        deck = Deck(
            id=deck_id,
            user_id=user_id,
            prompt="Test presentation about AI",
            status=DeckStatus.PENDING,
            style_preferences={"theme": "professional"},
            created_at=now,
        )

        assert deck.id == deck_id
        assert deck.user_id == user_id
        assert deck.prompt == "Test presentation about AI"
        assert deck.status == DeckStatus.PENDING
        assert deck.style_preferences == {"theme": "professional"}
        assert deck.slide_count == 0
        assert deck.template_type is None

    def test_can_be_cancelled_when_pending(self):
        """Test deck can be cancelled when pending."""
        deck = Deck(
            id=uuid4(),
            user_id=uuid4(),
            prompt="test",
            status=DeckStatus.PENDING,
            style_preferences={},
            created_at=datetime.now(timezone.utc),
        )

        assert deck.can_be_cancelled() is True

    def test_can_be_cancelled_when_planning(self):
        """Test deck can be cancelled when planning."""
        deck = Deck(
            id=uuid4(),
            user_id=uuid4(),
            prompt="test",
            status=DeckStatus.PLANNING,
            style_preferences={},
            created_at=datetime.now(timezone.utc),
        )

        assert deck.can_be_cancelled() is True

    def test_cannot_be_cancelled_when_generating(self):
        """Test deck cannot be cancelled when generating."""
        deck = Deck(
            id=uuid4(),
            user_id=uuid4(),
            prompt="test",
            status=DeckStatus.GENERATING,
            style_preferences={},
            created_at=datetime.now(timezone.utc),
        )

        assert deck.can_be_cancelled() is False

    def test_mark_as_completed_success(self):
        """Test marking deck as completed."""
        deck = Deck(
            id=uuid4(),
            user_id=uuid4(),
            prompt="test",
            status=DeckStatus.GENERATING,
            style_preferences={},
            created_at=datetime.now(timezone.utc),
        )

        deck.mark_as_completed()

        assert deck.status == DeckStatus.COMPLETED
        assert deck.completed_at is not None
        assert deck.updated_at is not None

    def test_mark_as_completed_invalid_status_raises_error(self):
        """Test marking non-generating deck as completed raises error."""
        deck = Deck(
            id=uuid4(),
            user_id=uuid4(),
            prompt="test",
            status=DeckStatus.PENDING,
            style_preferences={},
            created_at=datetime.now(timezone.utc),
        )

        with pytest.raises(
            ValueError, match="Can only complete decks that are generating"
        ):
            deck.mark_as_completed()

    def test_increment_slide_count_success(self):
        """Test incrementing slide count."""
        deck = Deck(
            id=uuid4(),
            user_id=uuid4(),
            prompt="test",
            status=DeckStatus.GENERATING,
            style_preferences={},
            created_at=datetime.now(timezone.utc),
            slide_count=5,
        )

        deck.increment_slide_count()

        assert deck.slide_count == 6
        assert deck.updated_at is not None

    def test_increment_slide_count_exceeds_maximum_raises_error(self):
        """Test incrementing slide count beyond maximum raises error."""
        deck = Deck(
            id=uuid4(),
            user_id=uuid4(),
            prompt="test",
            status=DeckStatus.GENERATING,
            style_preferences={},
            created_at=datetime.now(timezone.utc),
            slide_count=50,  # Already at maximum
        )

        with pytest.raises(ValueError, match="Maximum 50 slides per deck"):
            deck.increment_slide_count()


class TestSlideEntity:
    def test_slide_creation(self):
        """Test slide entity creation."""
        slide_id = uuid4()
        deck_id = uuid4()
        now = datetime.now(timezone.utc)

        slide = Slide(
            id=slide_id,
            deck_id=deck_id,
            order=1,
            title="Introduction",
            content_outline="Overview of the presentation topics",
            html_content=None,
            presenter_notes="Welcome the audience",
            template_filename="professional_slide.html",
            created_at=now,
        )

        assert slide.id == slide_id
        assert slide.deck_id == deck_id
        assert slide.order == 1
        assert slide.title == "Introduction"
        assert slide.html_content is None
        assert slide.template_filename == "professional_slide.html"

    def test_is_complete_with_html_content(self):
        """Test slide is complete when it has HTML content."""
        slide = Slide(
            id=uuid4(),
            deck_id=uuid4(),
            order=1,
            title="Test",
            content_outline="test",
            html_content="<h1>Test Slide</h1><p>Content here</p>",
            presenter_notes="",
            template_filename="content_slide.html",
            created_at=datetime.now(timezone.utc),
        )

        assert slide.is_complete() is True

    def test_is_not_complete_without_html_content(self):
        """Test slide is not complete without HTML content."""
        slide = Slide(
            id=uuid4(),
            deck_id=uuid4(),
            order=1,
            title="Test",
            content_outline="test",
            html_content=None,
            presenter_notes="",
            template_filename="content_slide.html",
            created_at=datetime.now(timezone.utc),
        )

        assert slide.is_complete() is False

    def test_is_not_complete_with_empty_html_content(self):
        """Test slide is not complete with empty HTML content."""
        slide = Slide(
            id=uuid4(),
            deck_id=uuid4(),
            order=1,
            title="Test",
            content_outline="test",
            html_content="   ",  # Only whitespace
            presenter_notes="",
            template_filename="content_slide.html",
            created_at=datetime.now(timezone.utc),
        )

        assert slide.is_complete() is False

    def test_can_be_edited(self):
        """Test slide can be edited."""
        slide = Slide(
            id=uuid4(),
            deck_id=uuid4(),
            order=1,
            title="Test",
            content_outline="test",
            html_content=None,
            presenter_notes="",
            template_filename="content_slide.html",
            created_at=datetime.now(timezone.utc),
        )

        # For now, always returns True
        assert slide.can_be_edited() is True

    def test_get_content_summary_with_html_content(self):
        """Test getting content summary from HTML content."""
        long_html = "<h1>Title</h1>" + "<p>Content line</p>" * 20  # Long HTML
        slide = Slide(
            id=uuid4(),
            deck_id=uuid4(),
            order=1,
            title="Test",
            content_outline="short outline",
            html_content=long_html,
            presenter_notes="",
            template_filename="content_slide.html",
            created_at=datetime.now(timezone.utc),
        )

        summary = slide.get_content_summary()
        assert len(summary) <= 203  # 200 chars + "..."
        assert "Title" in summary  # HTML tags should be stripped
        assert "<h1>" not in summary  # HTML tags should be removed

    def test_get_content_summary_without_html_content(self):
        """Test getting content summary from content outline."""
        long_outline = "This is a very long content outline " * 10  # Long outline
        slide = Slide(
            id=uuid4(),
            deck_id=uuid4(),
            order=1,
            title="Test",
            content_outline=long_outline,
            html_content=None,
            presenter_notes="",
            template_filename="content_slide.html",
            created_at=datetime.now(timezone.utc),
        )

        summary = slide.get_content_summary()
        assert len(summary) <= 203  # 200 chars + "..."
        assert "This is a very long" in summary
