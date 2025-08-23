from pydantic import BaseModel, Field
from typing import List, Optional


class PresentationRequest(BaseModel):
    topic: str = Field(
        ..., json_schema_extra={"example": "The Impact of AI on Marketing"}
    )
    audience: Optional[str] = Field(
        None,
        json_schema_extra={"example": "비즈니스 전문가"},
        description="발표의 목표 대상입니다.",
    )
    key_points: Optional[List[str]] = Field(
        None,
        json_schema_extra={"example": ["AI 소개", "마케팅 전략에서의 AI"]},
        description="발표에 포함할 핵심 내용 또는 섹션입니다.",
    )
    tone: Optional[str] = Field(
        None,
        json_schema_extra={"example": "격식"},
        description="발표의 원하는 톤(예: 격식, 캐주얼, 설득적)입니다.",
    )
    slide_count: int = Field(5, gt=0, le=10, json_schema_extra={"example": 5})
    model: Optional[str] = Field(
        "gpt-4o-mini", json_schema_extra={"example": "gpt-4o-mini"}
    )
    template_name: Optional[str] = Field(
        "modern", json_schema_extra={"example": "modern"}
    )

    user_provided_urls: Optional[List[str]] = Field(
        None, description="사용자가 연구를 위해 제공한 URL 목록입니다."
    )
    user_provided_text: Optional[str] = Field(
        None, description="사용자가 연구를 위해 직접 제공한 텍스트 내용입니다."
    )
    perform_web_search: bool = Field(
        False, description="추가 연구를 위해 웹 검색을 수행할지 여부입니다."
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
