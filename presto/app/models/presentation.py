from pydantic import BaseModel, Field
from typing import List, Optional


class PresentationRequest(BaseModel):
    topic: str = Field(
        ..., json_schema_extra={"example": "The Impact of AI on Marketing"}
    )
    slide_count: int = Field(5, gt=0, le=10, json_schema_extra={"example": 5})
    model: Optional[str] = Field(
        "gpt-4o-mini", json_schema_extra={"example": "gpt-4o-mini"}
    )
    theme: Optional[str] = Field("modern", json_schema_extra={"example": "modern"})

    user_provided_urls: Optional[List[str]] = Field(
        None, description="List of URLs provided by the user for research."
    )
    user_provided_text: Optional[str] = Field(
        None, description="Direct text content provided by the user for research."
    )
    perform_web_search: bool = Field(
        False, description="Whether to perform a web search for additional research."
    )


class GatheredResource(BaseModel):
    source: str = Field(
        ...,
        description="Source of the resource (e.g., 'web_search', 'user_url', 'user_text').",
    )
    content: str = Field(..., description="Raw content of the resource.")
    url: Optional[str] = Field(None, description="Original URL if applicable.")
    title: Optional[str] = Field(
        None, description="Title of the resource if available."
    )


class EnrichedContext(BaseModel):
    summary: str = Field(
        ..., description="A concise summary of all gathered resources."
    )
    raw_resources: List[GatheredResource] = Field(
        [], description="List of raw gathered resources."
    )


class SlideOutline(BaseModel):
    title: str
    layout: str


class PresentationOutline(BaseModel):
    slides: List[SlideOutline]


class SlideContent(BaseModel):
    title: str
    content: List[str]
