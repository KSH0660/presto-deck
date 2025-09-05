"""
Domain service for deck orchestration and complex business logic.

This service handles business logic that spans multiple entities or requires
coordination between different domain concepts.
"""

from typing import List, Optional
from uuid import UUID

from app.domain.entities.deck import Deck
from app.domain.entities.slide import Slide
from app.domain.value_objects.deck_status import DeckStatus
from app.domain.value_objects.template_type import TemplateType, SlideTemplate


class DeckOrchestrationService:
    """
    Domain service for orchestrating deck operations.

    Handles complex business logic that doesn't belong to a single entity,
    such as deck completion validation, slide ordering, and template selection.
    """

    @staticmethod
    def can_mark_deck_complete(
        deck: Deck, slides: List[Slide]
    ) -> tuple[bool, Optional[str]]:
        """
        Business rule: Determine if a deck can be marked as complete.

        A deck can be completed only if:
        1. It has at least one slide
        2. All slides have HTML content
        3. Deck is in GENERATING or EDITING status

        Args:
            deck: The deck to check
            slides: All slides belonging to the deck

        Returns:
            tuple[bool, Optional[str]]: (can_complete, reason_if_not)
        """
        if not deck.status.can_transition_to(DeckStatus.COMPLETED):
            return False, f"Cannot complete deck from {deck.status.value} status"

        if not slides:
            return False, "Deck must have at least one slide to be completed"

        incomplete_slides = [slide for slide in slides if not slide.is_complete()]
        if incomplete_slides:
            return False, f"Found {len(incomplete_slides)} incomplete slides"

        return True, None

    @staticmethod
    def calculate_slide_order(
        existing_slides: List[Slide], insert_position: Optional[int] = None
    ) -> int:
        """
        Business rule: Calculate the order for a new slide.

        Args:
            existing_slides: Current slides in the deck
            insert_position: Desired position (0-based), None for append

        Returns:
            int: The order value for the new slide
        """
        if not existing_slides:
            return 1

        max_order = max(slide.order for slide in existing_slides)

        if insert_position is None:
            # Append to end
            return max_order + 1

        # Insert at specific position - validate bounds
        if insert_position < 0:
            return 1
        elif insert_position >= len(existing_slides):
            return max_order + 1
        else:
            # Find the order value at the insert position
            sorted_slides = sorted(existing_slides, key=lambda s: s.order)
            if insert_position < len(sorted_slides):
                target_order = sorted_slides[insert_position].order
                return target_order
            else:
                return max_order + 1

    @staticmethod
    def reorder_slides(slides: List[Slide], new_order: List[UUID]) -> List[Slide]:
        """
        Business rule: Reorder slides according to new sequence.

        Args:
            slides: Current slides to reorder
            new_order: List of slide IDs in desired order

        Returns:
            List[Slide]: Slides with updated order values

        Raises:
            ValueError: If new_order doesn't match existing slides
        """
        slide_dict = {slide.id: slide for slide in slides if slide.id}

        if set(new_order) != set(slide_dict.keys()):
            raise ValueError("New order must contain exactly the same slide IDs")

        # Update order values
        reordered_slides = []
        for i, slide_id in enumerate(new_order, 1):
            slide = slide_dict[slide_id]
            # Create new slide instance with updated order
            updated_slide = Slide(
                id=slide.id,
                deck_id=slide.deck_id,
                order=i,
                title=slide.title,
                content_outline=slide.content_outline,
                html_content=slide.html_content,
                presenter_notes=slide.presenter_notes,
                template_filename=slide.template_filename,
                created_at=slide.created_at,
                updated_at=slide.updated_at,
            )
            reordered_slides.append(updated_slide)

        return reordered_slides

    @staticmethod
    def select_appropriate_template(
        template_type: TemplateType,
        slide_position: int,
        total_slides: int,
        available_templates: List[SlideTemplate],
    ) -> Optional[SlideTemplate]:
        """
        Business rule: Select the most appropriate template for a slide.

        Args:
            template_type: Desired template type
            slide_position: Position of slide (1-based)
            total_slides: Total number of slides
            available_templates: Available template options

        Returns:
            Optional[SlideTemplate]: Best matching template, or None if no match
        """
        # Filter templates by type compatibility
        compatible_templates = [
            template
            for template in available_templates
            if template.is_compatible_with(template_type)
        ]

        if not compatible_templates:
            return None

        # Business logic for template selection based on position
        if slide_position == 1:
            # First slide - prefer title templates
            title_templates = [
                t for t in compatible_templates if "title" in t.filename.lower()
            ]
            if title_templates:
                return title_templates[0]

        elif slide_position == total_slides:
            # Last slide - prefer conclusion templates
            conclusion_templates = [
                t
                for t in compatible_templates
                if any(
                    keyword in t.filename.lower()
                    for keyword in ["conclusion", "end", "thanks", "summary"]
                )
            ]
            if conclusion_templates:
                return conclusion_templates[0]

        # Default to content templates for middle slides
        content_templates = [
            t for t in compatible_templates if "content" in t.filename.lower()
        ]
        if content_templates:
            return content_templates[0]

        # Fallback to any compatible template
        return compatible_templates[0] if compatible_templates else None

    @staticmethod
    def validate_deck_constraints(deck: Deck, slides: List[Slide]) -> List[str]:
        """
        Business rule: Validate all deck constraints and return violations.

        Args:
            deck: The deck to validate
            slides: All slides in the deck

        Returns:
            List[str]: List of constraint violations (empty if all valid)
        """
        violations = []

        # Check slide count constraints
        if len(slides) > 50:
            violations.append("Deck exceeds maximum of 50 slides")

        if deck.slide_count != len(slides):
            violations.append(
                f"Deck slide count ({deck.slide_count}) doesn't match actual slides ({len(slides)})"
            )

        # Check slide ordering
        orders = [slide.order for slide in slides]
        if len(set(orders)) != len(orders):
            violations.append("Slides have duplicate order values")

        expected_orders = list(range(1, len(slides) + 1))
        if sorted(orders) != expected_orders:
            violations.append("Slide orders are not sequential starting from 1")

        # Check deck consistency
        wrong_deck_slides = [slide for slide in slides if slide.deck_id != deck.id]
        if wrong_deck_slides:
            violations.append(
                f"Found {len(wrong_deck_slides)} slides belonging to different decks"
            )

        return violations
