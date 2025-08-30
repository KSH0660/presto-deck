# app/core/rendering/add.py
"""새 슬라이드 생성 유틸."""


async def add_slide_content(add_prompt: str) -> dict:
    """프롬프트에 따라 새 슬라이드의 제목/HTML을 생성합니다."""
    # 테스트 친화적인 순수 함수: 외부 호출 없이 결과 반환
    return {
        "title": f"New Slide for: {add_prompt}",
        "html_content": "<div>New</div>",
    }
