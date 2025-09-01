from typing import Any, Dict, List
from pydantic import BaseModel


class SlideInfo(BaseModel):
    slide_number: int
    title: str
    type: str  # title|content|conclusion
    key_points: List[str]
    content_type: str  # text|chart|image|mixed
    estimated_duration: int


class DeckPlan(BaseModel):
    title: str
    slides: List[SlideInfo]
    total_slides: int
    estimated_duration: int
    target_audience: str


class SlideContent(BaseModel):
    title: str
    content: str
    html_content: str
    presenter_notes: str
    slide_number: int