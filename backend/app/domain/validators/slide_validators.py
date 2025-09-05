"""
Domain validators for slide-related business rules.
"""

from bleach.css_sanitizer import CSSSanitizer
from bleach.sanitizer import Cleaner


class SlideValidators:
    ALLOWED_TAGS = [
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "p",
        "br",
        "div",
        "span",
        "ul",
        "ol",
        "li",
        "strong",
        "b",
        "em",
        "i",
        "blockquote",
        "code",
        "pre",
        "img",
        "figure",
        "figcaption",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
    ]

    ALLOWED_ATTRIBUTES = {
        "*": ["class", "id", "style"],
        "img": ["src", "alt", "width", "height"],
        "a": ["href", "title"],
    }

    cleaner = Cleaner(
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        css_sanitizer=CSSSanitizer(),
    )

    @staticmethod
    def validate_content_outline(outline: str) -> None:
        if not outline or not outline.strip():
            raise ValueError("Slide content outline cannot be empty")
        if len(outline.strip()) < 5:
            raise ValueError("Slide content outline must be at least 5 characters")
        if len(outline) > 2000:
            raise ValueError("Slide content outline cannot exceed 2000 characters")

    @classmethod
    def sanitize_html_content(cls, html_content: str) -> str:
        if not html_content:
            raise ValueError("HTML content cannot be empty")
        return cls.cleaner.clean(html_content)

    @staticmethod
    def validate_slide_order(order: int, total_slides: int) -> None:
        """Validate slide order is within valid range."""
        if order < 1:
            raise ValueError("Slide order must be at least 1")

        if order > total_slides + 1:
            raise ValueError(
                f"Slide order {order} exceeds maximum allowed {total_slides + 1}"
            )
