"""
Pydantic models for LangChain structured output.
"""

from typing import List
from pydantic import BaseModel, Field


class TemplateMatch(BaseModel):
    """A single template match with reasoning."""

    filename: str = Field(
        description="The HTML template filename (e.g., 'title_slide.html')"
    )
    relevance_score: float = Field(
        description="Relevance score from 0.0 to 1.0 indicating how well this template matches the slide content",
        ge=0.0,
        le=1.0,
    )
    reasoning: str = Field(
        description="Brief explanation of why this template is suitable for the slide"
    )


class TemplateSelection(BaseModel):
    """Template selection result with top 3 matches."""

    slide_type: str = Field(
        description="The identified type of slide (e.g., 'intro', 'content', 'comparison', 'conclusion')"
    )
    selected_templates: List[TemplateMatch] = Field(
        description="Top 3 most suitable templates ranked by relevance",
        min_length=1,
        max_length=3,
    )
    overall_reasoning: str = Field(
        description="Overall explanation of the template selection strategy for this slide"
    )


class SlideTemplateAssignment(BaseModel):
    """Assignment of templates to each slide in the deck."""

    slide_order: int = Field(description="The order/position of the slide (1-based)")
    slide_title: str = Field(description="The title of the slide")
    primary_template: str = Field(description="The primary template filename to use")
    alternative_templates: List[str] = Field(
        description="Alternative template filenames as fallbacks",
        max_length=2,
        default=[],
    )
    content_adaptation_notes: str = Field(
        description="Notes on how to adapt the content for the selected template"
    )


class DeckTemplateSelections(BaseModel):
    """Complete template selections for all slides in a deck."""

    deck_theme: str = Field(description="Overall theme or style of the presentation")
    slide_assignments: List[SlideTemplateAssignment] = Field(
        description="Template assignments for each slide in order"
    )
    template_usage_summary: dict[str, int] = Field(
        description="Count of how many times each template is used", default={}
    )
