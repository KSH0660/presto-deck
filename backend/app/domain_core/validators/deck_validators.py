"""
Domain validators for deck-related business rules.
"""

from typing import Dict, Any


class DeckValidators:
    @staticmethod
    def validate_prompt(prompt: str) -> None:
        """Validate deck prompt meets business requirements."""
        if not prompt or not prompt.strip():
            raise ValueError("Deck prompt cannot be empty")

        if len(prompt.strip()) < 10:
            raise ValueError("Deck prompt must be at least 10 characters")

        if len(prompt) > 5000:
            raise ValueError("Deck prompt cannot exceed 5000 characters")

    @staticmethod
    def validate_style_preferences(preferences: Dict[str, Any]) -> None:
        """Validate style preferences structure."""
        allowed_keys = {
            "theme",
            "color_scheme",
            "font_family",
            "slide_layout",
            "animation_style",
        }

        invalid_keys = set(preferences.keys()) - allowed_keys
        if invalid_keys:
            raise ValueError(f"Invalid style preference keys: {invalid_keys}")

        if "theme" in preferences:
            valid_themes = [
                "minimal",
                "professional",
                "creative",
                "academic",
                "corporate",
                "startup",
            ]
            if preferences["theme"] not in valid_themes:
                raise ValueError(f"Theme must be one of: {valid_themes}")

    @staticmethod
    def validate_deck_plan(plan: Dict[str, Any]) -> None:
        """Validate deck plan structure from LLM."""
        if not plan:
            raise ValueError("Deck plan cannot be empty")

        if "slides" not in plan:
            raise ValueError("Deck plan must contain slides")

        slides = plan["slides"]
        if not isinstance(slides, list) or len(slides) == 0:
            raise ValueError("Deck plan must contain at least one slide")

        if len(slides) > 50:
            raise ValueError("Deck cannot contain more than 50 slides")

        for i, slide in enumerate(slides):
            if not isinstance(slide, dict):
                raise ValueError(f"Slide {i+1} must be a dictionary")

            if "title" not in slide:
                raise ValueError(f"Slide {i+1} must have a title")

            if "content" not in slide:
                raise ValueError(f"Slide {i+1} must have content")
