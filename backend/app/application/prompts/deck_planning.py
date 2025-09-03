"""
Deck planning prompts and structured output models.

Contains all prompts and Pydantic models for deck generation and planning.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


# ---------- STRUCTURED OUTPUT MODELS ----------
class SlideOutline(BaseModel):
    """Structured outline for a single slide."""

    title: str = Field(..., description="Slide title")
    content: str = Field(..., description="Detailed content outline")
    notes: str = Field(..., description="Presenter notes and speaking points")
    order: int = Field(..., description="Slide order in presentation")


class DeckPlan(BaseModel):
    """Structured plan for complete presentation deck."""

    title: str = Field(..., description="Presentation title")
    theme: str = Field(..., description="Suggested theme based on content")
    target_audience: str = Field(..., description="Identified target audience")
    estimated_duration: int = Field(
        ..., description="Estimated presentation duration in minutes"
    )
    slides: List[SlideOutline] = Field(..., description="List of slide outlines")

    # Optional metadata
    key_takeaways: List[str] = Field(
        default_factory=list, description="Key messages audience should remember"
    )
    suggested_flow: str = Field(
        default="", description="Narrative flow and transitions"
    )


# ---------- PROMPT TEMPLATES ----------
class DeckPlanningPrompts:
    """Centralized prompt templates for deck planning."""

    @staticmethod
    def get_system_prompt() -> str:
        """System prompt for deck planning."""
        return """
You are an expert presentation designer with deep knowledge of effective storytelling,
audience engagement, and visual communication principles.

Your task is to create comprehensive presentation plans that:
- Follow clear narrative structure (problem → solution → benefits)
- Engage the specific target audience
- Include practical, actionable content
- Maintain professional standards
- Optimize for the intended presentation duration

Always consider:
- Opening: Hook the audience and set context
- Body: Logical flow with supporting evidence
- Conclusion: Clear call-to-action or key takeaways
- Transitions: Smooth connections between concepts

Return only valid JSON matching the DeckPlan schema.
"""

    @staticmethod
    def get_user_prompt(
        user_prompt: str,
        style_preferences: Optional[Dict[str, Any]] = None,
        slide_count: Optional[int] = None,
        sources: Optional[List[str]] = None,
    ) -> str:
        """Generate user prompt for deck planning."""

        base_prompt = f"""
Create a comprehensive presentation plan for: {user_prompt}

Requirements:
- Professional and engaging content
- Clear narrative flow appropriate for business/educational context
- Include practical examples and actionable insights where relevant
- Optimize slide count for content depth vs. audience attention span
"""

        # Add style preferences if provided
        if style_preferences:
            base_prompt += f"\nStyle preferences: {style_preferences}"

        # Add slide count guidance if provided
        if slide_count:
            base_prompt += f"\nTarget slide count: approximately {slide_count} slides"
        else:
            base_prompt += "\nSlide count: optimize for content (typically 8-15 slides)"

        # Add source materials if provided
        if sources:
            base_prompt += "\nReference materials to consider:\n"
            for i, source in enumerate(sources, 1):
                base_prompt += f"{i}. {source}\n"

        base_prompt += """
Ensure the presentation has:
1. Strong opening that establishes relevance
2. Logical progression of ideas
3. Supporting evidence and examples
4. Clear conclusion with actionable takeaways
"""

        return base_prompt

    @staticmethod
    def get_refinement_prompt(original_plan: DeckPlan, feedback: str) -> str:
        """Generate prompt for refining an existing deck plan."""
        return f"""
Refine this presentation plan based on the feedback provided:

Original Plan:
Title: {original_plan.title}
Theme: {original_plan.theme}
Slides: {len(original_plan.slides)} slides

Feedback: {feedback}

Please improve the plan while maintaining its core structure and message.
Focus on addressing the specific feedback points while preserving the
narrative flow and key takeaways.
"""


# ---------- TEMPLATE SELECTION ----------
class TemplateRecommendation(BaseModel):
    """Structured recommendation for presentation template."""

    template_type: str = Field(..., description="Recommended template type")
    reasoning: str = Field(..., description="Why this template fits the content")
    color_scheme: str = Field(..., description="Suggested color scheme")
    font_pairing: str = Field(..., description="Recommended font combination")
    visual_style: str = Field(..., description="Overall visual approach")


class TemplateSelectionPrompts:
    """Prompts for template and design selection."""

    @staticmethod
    def get_system_prompt() -> str:
        """System prompt for template selection."""
        return """
You are an expert visual designer specializing in presentation design.
Your expertise covers typography, color theory, visual hierarchy, and audience psychology.

Analyze the presentation content and recommend the most appropriate template
that will enhance the message delivery and audience engagement.

Consider:
- Content type (technical, creative, formal, casual)
- Target audience (executives, students, peers, general public)
- Presentation context (boardroom, conference, classroom, online)
- Visual elements needed (charts, images, text-heavy, minimal)

Return only valid JSON matching the TemplateRecommendation schema.
"""

    @staticmethod
    def get_user_prompt(deck_plan: DeckPlan, context: Optional[str] = None) -> str:
        """Generate prompt for template recommendation."""

        prompt = f"""
Recommend the best presentation template for this content:

Title: {deck_plan.title}
Theme: {deck_plan.theme}
Target Audience: {deck_plan.target_audience}
Duration: {deck_plan.estimated_duration} minutes
Number of Slides: {len(deck_plan.slides)}

Content Overview:
"""

        for slide in deck_plan.slides[:3]:  # Include first 3 slides as sample
            prompt += f"- {slide.title}: {slide.content[:100]}...\n"

        if context:
            prompt += f"\nPresentation Context: {context}"

        prompt += """

Please recommend:
1. The most suitable template type
2. Appropriate color scheme
3. Font pairing that enhances readability
4. Visual style that matches the content tone

Consider both aesthetics and functionality for the intended audience and context.
"""

        return prompt
