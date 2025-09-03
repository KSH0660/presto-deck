"""
Domain validators for slide-related business rules.
"""

import bleach


class SlideValidators:
    # Allowed HTML tags for slide content
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

    @staticmethod
    def validate_content_outline(outline: str) -> None:
        """Validate slide content outline meets business requirements."""
        if not outline or not outline.strip():
            raise ValueError("Slide content outline cannot be empty")

        if len(outline.strip()) < 5:
            raise ValueError("Slide content outline must be at least 5 characters")

        if len(outline) > 2000:
            raise ValueError("Slide content outline cannot exceed 2000 characters")

    @staticmethod
    def sanitize_html_content(html_content: str) -> str:
        """Sanitize HTML content to prevent XSS attacks."""
        if not html_content:
            raise ValueError("HTML content cannot be empty")

        # Use bleach to sanitize HTML
        clean_html = bleach.clean(
            html_content,
            tags=SlideValidators.ALLOWED_TAGS,
            attributes=SlideValidators.ALLOWED_ATTRIBUTES,
            strip=True,
        )

        if len(clean_html.strip()) < 10:
            raise ValueError("HTML content too short after sanitization")

        return clean_html

    @staticmethod
    def validate_slide_order(order: int, total_slides: int) -> None:
        """Validate slide order is within valid range."""
        if order < 1:
            raise ValueError("Slide order must be at least 1")

        if order > total_slides + 1:
            raise ValueError(
                f"Slide order {order} exceeds maximum allowed {total_slides + 1}"
            )
