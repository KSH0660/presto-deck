"""
Unit tests for domain validators.
"""

import pytest
from app.domain_core.validators.deck_validators import DeckValidators
from app.domain_core.validators.slide_validators import SlideValidators


class TestDeckValidators:
    def test_validate_prompt_success(self):
        """Test valid prompt passes validation."""
        valid_prompt = "Create a presentation about machine learning basics"
        # Should not raise any exception
        DeckValidators.validate_prompt(valid_prompt)

    def test_validate_prompt_empty_raises_error(self):
        """Test empty prompt raises validation error."""
        with pytest.raises(ValueError, match="Deck prompt cannot be empty"):
            DeckValidators.validate_prompt("")

        with pytest.raises(ValueError, match="Deck prompt cannot be empty"):
            DeckValidators.validate_prompt("   ")  # Only whitespace

    def test_validate_prompt_too_short_raises_error(self):
        """Test too short prompt raises validation error."""
        with pytest.raises(ValueError, match="at least 10 characters"):
            DeckValidators.validate_prompt("short")

    def test_validate_prompt_too_long_raises_error(self):
        """Test too long prompt raises validation error."""
        long_prompt = "x" * 5001
        with pytest.raises(ValueError, match="cannot exceed 5000 characters"):
            DeckValidators.validate_prompt(long_prompt)

    def test_validate_style_preferences_success(self):
        """Test valid style preferences pass validation."""
        valid_prefs = {
            "theme": "professional",
            "color_scheme": "blue",
            "font_family": "Arial",
        }
        # Should not raise any exception
        DeckValidators.validate_style_preferences(valid_prefs)

    def test_validate_style_preferences_invalid_keys_raises_error(self):
        """Test invalid keys in style preferences raise error."""
        invalid_prefs = {"invalid_key": "value"}
        with pytest.raises(ValueError, match="Invalid style preference keys"):
            DeckValidators.validate_style_preferences(invalid_prefs)

    def test_validate_style_preferences_invalid_theme_raises_error(self):
        """Test invalid theme raises error."""
        invalid_prefs = {"theme": "invalid_theme"}
        with pytest.raises(ValueError, match="Theme must be one of"):
            DeckValidators.validate_style_preferences(invalid_prefs)

    def test_validate_deck_plan_success(self):
        """Test valid deck plan passes validation."""
        valid_plan = {
            "title": "Test Presentation",
            "slides": [
                {"title": "Slide 1", "content": "Content 1"},
                {"title": "Slide 2", "content": "Content 2"},
            ],
        }
        # Should not raise any exception
        DeckValidators.validate_deck_plan(valid_plan)

    def test_validate_deck_plan_empty_raises_error(self):
        """Test empty deck plan raises error."""
        with pytest.raises(ValueError, match="Deck plan cannot be empty"):
            DeckValidators.validate_deck_plan({})

    def test_validate_deck_plan_no_slides_raises_error(self):
        """Test deck plan without slides raises error."""
        invalid_plan = {"title": "Test"}
        with pytest.raises(ValueError, match="must contain slides"):
            DeckValidators.validate_deck_plan(invalid_plan)

    def test_validate_deck_plan_empty_slides_raises_error(self):
        """Test deck plan with empty slides array raises error."""
        invalid_plan = {"slides": []}
        with pytest.raises(ValueError, match="at least one slide"):
            DeckValidators.validate_deck_plan(invalid_plan)

    def test_validate_deck_plan_too_many_slides_raises_error(self):
        """Test deck plan with too many slides raises error."""
        invalid_plan = {
            "slides": [
                {"title": f"Slide {i}", "content": f"Content {i}"} for i in range(51)
            ]  # 51 slides, max is 50
        }
        with pytest.raises(ValueError, match="cannot contain more than 50 slides"):
            DeckValidators.validate_deck_plan(invalid_plan)


class TestSlideValidators:
    def test_validate_content_outline_success(self):
        """Test valid content outline passes validation."""
        valid_outline = "This slide covers machine learning basics including supervised and unsupervised learning."
        # Should not raise any exception
        SlideValidators.validate_content_outline(valid_outline)

    def test_validate_content_outline_empty_raises_error(self):
        """Test empty content outline raises error."""
        with pytest.raises(ValueError, match="cannot be empty"):
            SlideValidators.validate_content_outline("")

    def test_validate_content_outline_too_short_raises_error(self):
        """Test too short content outline raises error."""
        with pytest.raises(ValueError, match="at least 5 characters"):
            SlideValidators.validate_content_outline("hi")

    def test_validate_content_outline_too_long_raises_error(self):
        """Test too long content outline raises error."""
        long_outline = "x" * 2001
        with pytest.raises(ValueError, match="cannot exceed 2000 characters"):
            SlideValidators.validate_content_outline(long_outline)

    def test_sanitize_html_content_success(self):
        """Test valid HTML gets sanitized properly."""
        html_content = "<h1>Title</h1><p>Content with <strong>bold</strong> text.</p>"
        result = SlideValidators.sanitize_html_content(html_content)
        assert "<h1>" in result
        assert "<strong>" in result

    def test_sanitize_html_content_removes_unsafe_tags(self):
        """Test unsafe HTML tags are removed."""
        html_content = "<script>alert('xss')</script><h1>Safe Title</h1>"
        result = SlideValidators.sanitize_html_content(html_content)
        assert "<script>" not in result
        assert "<h1>Safe Title</h1>" in result

    def test_sanitize_html_content_empty_raises_error(self):
        """Test empty HTML content raises error."""
        with pytest.raises(ValueError, match="HTML content cannot be empty"):
            SlideValidators.sanitize_html_content("")

    def test_validate_slide_order_success(self):
        """Test valid slide order passes validation."""
        # Should not raise any exception
        SlideValidators.validate_slide_order(1, 5)  # Order 1 in deck of 5 slides
        SlideValidators.validate_slide_order(5, 5)  # Last slide

    def test_validate_slide_order_too_low_raises_error(self):
        """Test slide order less than 1 raises error."""
        with pytest.raises(ValueError, match="must be at least 1"):
            SlideValidators.validate_slide_order(0, 5)

    def test_validate_slide_order_too_high_raises_error(self):
        """Test slide order exceeding maximum raises error."""
        with pytest.raises(ValueError, match="exceeds maximum allowed"):
            SlideValidators.validate_slide_order(7, 5)  # Order 7 in deck of 5 slides
