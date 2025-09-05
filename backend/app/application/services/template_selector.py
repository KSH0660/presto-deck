"""
Template Selection Service - Handles template selection logic.

This service encapsulates the business logic for selecting appropriate
templates based on various criteria and constraints.
"""

from typing import List, Optional, Dict, Any

from app.domain.value_objects.template_type import TemplateType, SlideTemplate
from app.application.ports import TemplateServicePort


class TemplateSelectionService:
    """
    Application service for template selection and management.

    Coordinates template selection logic with external template systems
    and applies business rules for template matching.
    """

    def __init__(self, template_service: TemplateServicePort):
        self.template_service = template_service

    async def select_deck_template_type(
        self,
        prompt: str,
        style_preferences: Dict[str, Any],
        user_preferences: Optional[Dict[str, Any]] = None,
    ) -> TemplateType:
        """
        Select the most appropriate template type for a deck.

        Args:
            prompt: The user's prompt for deck generation
            style_preferences: Style preferences from the request
            user_preferences: Optional user-specific preferences

        Returns:
            TemplateType: The selected template type
        """
        # Priority 1: Explicit template type from style preferences
        if style_preferences and "template_type" in style_preferences:
            requested_type = style_preferences["template_type"].lower()
            for template_type in TemplateType:
                if template_type.value == requested_type:
                    return template_type

        # Priority 2: User's default preferences
        if user_preferences and "default_template_type" in user_preferences:
            default_type = user_preferences["default_template_type"].lower()
            for template_type in TemplateType:
                if template_type.value == default_type:
                    return template_type

        # Priority 3: Analyze prompt content for template type hints
        prompt_lower = prompt.lower()

        # Business rules for template type selection based on content
        if any(
            keyword in prompt_lower
            for keyword in ["business", "corporate", "company", "professional"]
        ):
            return TemplateType.CORPORATE
        elif any(
            keyword in prompt_lower
            for keyword in ["startup", "pitch", "funding", "investor"]
        ):
            return TemplateType.STARTUP
        elif any(
            keyword in prompt_lower
            for keyword in ["research", "academic", "study", "paper"]
        ):
            return TemplateType.ACADEMIC
        elif any(
            keyword in prompt_lower
            for keyword in ["creative", "design", "art", "innovative"]
        ):
            return TemplateType.CREATIVE
        elif any(
            keyword in prompt_lower
            for keyword in ["simple", "minimal", "clean", "basic"]
        ):
            return TemplateType.MINIMAL
        else:
            # Default to professional for general use
            return TemplateType.PROFESSIONAL

    async def get_slide_templates_for_deck(
        self, template_type: TemplateType, slide_count: int
    ) -> List[SlideTemplate]:
        """
        Get appropriate slide templates for a deck.

        Args:
            template_type: The template type for the deck
            slide_count: Number of slides in the deck

        Returns:
            List[SlideTemplate]: Available templates for the deck
        """
        # Get all available templates from the template service
        available_templates = await self.template_service.get_available_templates(
            template_type=template_type.value
        )

        # Convert to SlideTemplate objects
        slide_templates = []
        for template_data in available_templates:
            slide_template = SlideTemplate(
                filename=template_data["filename"],
                template_type=template_type,
                display_name=template_data.get(
                    "display_name", template_data["filename"]
                ),
            )
            slide_templates.append(slide_template)

        return slide_templates

    async def select_slide_template(
        self,
        template_type: TemplateType,
        slide_position: int,
        total_slides: int,
        slide_content_type: Optional[str] = None,
    ) -> Optional[SlideTemplate]:
        """
        Select the most appropriate template for a specific slide.

        Args:
            template_type: The deck's template type
            slide_position: Position of the slide (1-based)
            total_slides: Total number of slides in the deck
            slide_content_type: Optional hint about slide content type

        Returns:
            Optional[SlideTemplate]: The selected template, or None if no match
        """
        # Get available templates for this template type
        available_templates = await self.get_slide_templates_for_deck(
            template_type=template_type, slide_count=total_slides
        )

        if not available_templates:
            return None

        # Use domain service for template selection logic
        from app.domain.services.deck_orchestration import DeckOrchestrationService

        selected_template = DeckOrchestrationService.select_appropriate_template(
            template_type=template_type,
            slide_position=slide_position,
            total_slides=total_slides,
            available_templates=available_templates,
        )

        return selected_template

    async def get_template_style_preferences(
        self,
        template_type: TemplateType,
        custom_preferences: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get merged style preferences for a template type.

        Args:
            template_type: The template type
            custom_preferences: Optional custom style preferences

        Returns:
            Dict[str, Any]: Merged style preferences
        """
        # Start with template type defaults
        default_preferences = template_type.get_default_style_preferences()

        # Merge with custom preferences if provided
        if custom_preferences:
            merged_preferences = {**default_preferences, **custom_preferences}
        else:
            merged_preferences = default_preferences

        return merged_preferences

    async def validate_template_compatibility(
        self, template_filename: str, template_type: TemplateType
    ) -> bool:
        """
        Validate that a template file is compatible with a template type.

        Args:
            template_filename: The template file to validate
            template_type: The expected template type

        Returns:
            bool: True if compatible
        """
        try:
            # Get template metadata from the template service
            available_templates = await self.template_service.get_available_templates(
                template_type=template_type.value
            )

            # Check if the template exists and matches the type
            for template_data in available_templates:
                if template_data["filename"] == template_filename:
                    return True

            return False
        except Exception:
            # If we can't validate, assume incompatible
            return False
