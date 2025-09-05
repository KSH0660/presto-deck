"""
Template type and slide template value objects.
"""

from enum import Enum
from typing import Dict, Any


class TemplateType(Enum):
    """
    High-level template categories for deck styling.
    """

    MINIMAL = "minimal"
    PROFESSIONAL = "professional"
    CREATIVE = "creative"
    ACADEMIC = "academic"
    CORPORATE = "corporate"
    STARTUP = "startup"

    def get_default_style_preferences(self) -> Dict[str, Any]:
        """
        Business rule: Get default style preferences for each template type.

        Returns:
            Dict[str, Any]: Default style configuration
        """
        defaults = {
            self.MINIMAL: {
                "color_scheme": "monochrome",
                "font_family": "sans-serif",
                "layout_density": "spacious",
            },
            self.PROFESSIONAL: {
                "color_scheme": "navy_blue",
                "font_family": "serif",
                "layout_density": "balanced",
            },
            self.CREATIVE: {
                "color_scheme": "vibrant",
                "font_family": "modern",
                "layout_density": "dynamic",
            },
            self.ACADEMIC: {
                "color_scheme": "classic",
                "font_family": "serif",
                "layout_density": "content_heavy",
            },
            self.CORPORATE: {
                "color_scheme": "corporate_blue",
                "font_family": "sans-serif",
                "layout_density": "structured",
            },
            self.STARTUP: {
                "color_scheme": "gradient",
                "font_family": "modern",
                "layout_density": "energetic",
            },
        }
        return defaults.get(self, {})


class SlideTemplate:
    """
    Value object representing a specific slide template file and its metadata.
    """

    def __init__(self, filename: str, template_type: TemplateType, display_name: str):
        """
        Initialize slide template.

        Args:
            filename: Template file name (e.g., "corporate_title.html")
            template_type: High-level template category
            display_name: Human-readable name for UI
        """
        if not filename or not filename.endswith(".html"):
            raise ValueError("Template filename must be a valid HTML file")

        self.filename = filename
        self.template_type = template_type
        self.display_name = display_name

    def is_compatible_with(self, template_type: TemplateType) -> bool:
        """
        Business rule: Check if this template is compatible with a template type.

        Args:
            template_type: The template type to check compatibility with

        Returns:
            bool: True if compatible
        """
        return self.template_type == template_type

    def __eq__(self, other) -> bool:
        """Equality based on filename."""
        if not isinstance(other, SlideTemplate):
            return False
        return self.filename == other.filename

    def __hash__(self) -> int:
        """Hash based on filename."""
        return hash(self.filename)

    def __str__(self) -> str:
        """String representation."""
        return f"{self.display_name} ({self.filename})"
