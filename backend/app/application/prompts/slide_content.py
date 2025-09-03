"""
Slide content generation prompts and structured output models.

Contains prompts and models for generating individual slide content, HTML, and formatting.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


# ---------- STRUCTURED OUTPUT MODELS ----------
class SlideContent(BaseModel):
    """Structured content for a slide."""

    title: str = Field(..., description="Final slide title")
    html_content: str = Field(..., description="HTML content for the slide")
    presenter_notes: str = Field(..., description="Speaking notes for presenter")
    visual_elements: List[str] = Field(
        default_factory=list,
        description="Suggested visual elements (images, charts, etc.)",
    )
    accessibility_notes: str = Field(
        default="", description="Accessibility considerations for this slide"
    )


class SlideHTMLStructure(BaseModel):
    """Structured HTML generation for slide content."""

    semantic_html: str = Field(..., description="Clean, semantic HTML content")
    css_classes: List[str] = Field(..., description="CSS classes used")
    accessibility_attributes: Dict[str, str] = Field(
        default_factory=dict, description="ARIA and accessibility attributes"
    )
    content_structure: str = Field(
        ..., description="Description of content organization"
    )


# ---------- PROMPT TEMPLATES ----------
class SlideContentPrompts:
    """Centralized prompt templates for slide content generation."""

    @staticmethod
    def get_system_prompt() -> str:
        """System prompt for slide content generation."""
        return """
You are an expert content creator and presentation designer specializing in
creating engaging, accessible, and professionally formatted slide content.

Your expertise includes:
- Clear, compelling copywriting
- Visual hierarchy and information design
- Accessibility standards (WCAG guidelines)
- HTML semantic structure
- Audience-appropriate tone and language

Create content that:
- Follows the "one main idea per slide" principle
- Uses clear, concise language
- Includes engaging visual descriptions
- Maintains consistent tone and style
- Optimizes for both visual appeal and accessibility

Return only valid JSON matching the SlideContent schema.
"""

    @staticmethod
    def get_user_prompt(
        title: str,
        content_outline: str,
        template_type: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate user prompt for slide content creation."""

        prompt = f"""
Generate comprehensive slide content for:

Title: {title}
Content Outline: {content_outline}
Template Style: {template_type}
"""

        if context:
            if context.get("target_audience"):
                prompt += f"Target Audience: {context['target_audience']}\n"
            if context.get("presentation_tone"):
                prompt += f"Tone: {context['presentation_tone']}\n"
            if context.get("slide_position"):
                prompt += f"Position in Deck: {context['slide_position']}\n"

        prompt += """
Requirements:
- Create engaging, scannable content (bullet points, short paragraphs)
- Include specific examples or data points where appropriate
- Write presenter notes that add value beyond what's on screen
- Suggest visual elements that would enhance understanding
- Ensure content is appropriate for the intended audience
- Maintain professional yet engaging tone

Focus on clarity, engagement, and actionable insights.
"""

        return prompt

    @staticmethod
    def get_html_generation_prompt(
        slide_content: SlideContent, template_type: str
    ) -> str:
        """Generate prompt specifically for HTML content creation."""

        return f"""
Generate semantic, accessible HTML content for this slide:

Title: {slide_content.title}
Template: {template_type}

Content to convert to HTML:
{slide_content.html_content}

Presenter Notes (for context):
{slide_content.presenter_notes}

Visual Elements to incorporate:
{', '.join(slide_content.visual_elements)}

Requirements:
- Use semantic HTML5 elements (header, main, section, article, etc.)
- Include appropriate CSS classes for the {template_type} template
- Add ARIA labels and accessibility attributes
- Structure content with proper heading hierarchy (h2, h3, etc.)
- Use lists, emphasis, and other semantic markup appropriately
- No external scripts, images, or unsafe content
- Clean, well-indented HTML structure

Return the HTML content only (no <html>, <head>, or <body> wrapper tags).
The content should be ready for injection into a slide container.
"""


class SlideHTMLPrompts:
    """Specialized prompts for HTML generation."""

    @staticmethod
    def get_system_prompt() -> str:
        """System prompt for HTML generation."""
        return """
You are an expert frontend developer specializing in semantic HTML and accessibility.

Your expertise includes:
- Semantic HTML5 structure
- WCAG accessibility guidelines
- Clean, maintainable code
- CSS class naming conventions
- Cross-browser compatibility

Generate HTML that is:
- Semantically correct and meaningful
- Fully accessible with ARIA attributes
- Clean and well-structured
- Ready for CSS styling
- Safe and secure (no external resources)

Return only valid JSON matching the SlideHTMLStructure schema.
"""

    @staticmethod
    def get_regeneration_prompt(
        current_html: str, feedback: str, template_type: str
    ) -> str:
        """Generate prompt for improving existing HTML."""

        return f"""
Improve this slide HTML based on feedback:

Current HTML:
{current_html}

Template Type: {template_type}
Feedback: {feedback}

Please revise the HTML to address the feedback while maintaining:
- Semantic structure
- Accessibility standards
- Template compatibility
- Clean, readable code

Focus on the specific issues mentioned in the feedback.
"""


# ---------- CONTENT REFINEMENT ----------
class ContentRefinementPrompts:
    """Prompts for refining and improving slide content."""

    @staticmethod
    def get_tone_adjustment_prompt(
        content: str, current_tone: str, target_tone: str
    ) -> str:
        """Generate prompt for adjusting content tone."""

        return f"""
Adjust the tone of this slide content:

Current content:
{content}

Current tone: {current_tone}
Target tone: {target_tone}

Rewrite the content to match the target tone while:
- Preserving all key information and facts
- Maintaining clarity and engagement
- Keeping the same content structure
- Ensuring appropriateness for business context

The revised content should feel natural and authentic in the new tone.
"""

    @staticmethod
    def get_length_adjustment_prompt(
        content: str, target_length: str  # "shorter", "longer", "more_detailed"
    ) -> str:
        """Generate prompt for adjusting content length."""

        length_instructions = {
            "shorter": "Make the content more concise while preserving key points",
            "longer": "Expand the content with more details and examples",
            "more_detailed": "Add specific examples, data, and supporting information",
        }

        instruction = length_instructions.get(
            target_length, "Adjust the content length appropriately"
        )

        return f"""
Revise this slide content to be {target_length}:

Current content:
{content}

Instructions: {instruction}

Ensure the revised content:
- Maintains the core message and value
- Remains engaging and scannable
- Fits well within a single slide
- Uses appropriate visual hierarchy
"""
