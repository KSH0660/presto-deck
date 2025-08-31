"""슬라이드 도메인 엔티티"""

from typing import Optional
from pydantic import BaseModel
from app.domain.value_objects.content import SlideContent


class Slide(BaseModel):
    """슬라이드 엔티티"""

    id: int
    content: SlideContent
    template_name: Optional[str] = None
    html_content: Optional[str] = None
    version: int = 1
    status: str = "draft"  # draft, completed, failed

    def update_content(self, new_content: SlideContent) -> None:
        """슬라이드 내용 업데이트"""
        self.content = new_content
        self.version += 1
        self.status = "draft"  # 수정 시 다시 draft 상태

    def render_with_template(self, template_name: str, html_content: str) -> None:
        """템플릿으로 렌더링 완료"""
        self.template_name = template_name
        self.html_content = html_content
        self.status = "completed"
        self.version += 1

    def mark_as_failed(self) -> None:
        """렌더링 실패로 마킹"""
        self.status = "failed"
        self.version += 1

    @property
    def is_rendered(self) -> bool:
        """렌더링 완료 여부"""
        return self.html_content is not None and self.status == "completed"

    @property
    def is_draft(self) -> bool:
        """드래프트 상태 여부"""
        return self.status == "draft"
