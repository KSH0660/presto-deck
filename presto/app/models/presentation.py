from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class PresentationRequest(BaseModel):
    topic: str = Field(..., json_schema_extra={"example": "The Impact of AI on Marketing"})
    slide_count: int = Field(5, gt=0, le=10, json_schema_extra={"example": 5})
    model: Optional[str] = Field("gpt-4o-mini", json_schema_extra={"example": "gpt-4o-mini"})
    theme: Optional[str] = Field("modern", json_schema_extra={"example": "modern"})

class SlideOutline(BaseModel):
    title: str
    layout: str

class PresentationOutline(BaseModel):
    slides: List[SlideOutline]
     
class SlideContent(BaseModel):
    title: str
    content: List[str] 
 