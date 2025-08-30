# app/core/rendering/edit.py
"""슬라이드 HTML 편집 유틸.

LLM을 사용해 편집을 시도하고, 실패 시 간단한 휴리스틱으로 폴백합니다.
"""

import logging
from typing import Optional

from app.core.providers.llm import make_llm
from app.core.rendering.prompts import EDIT_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


async def edit_slide_content(
    original_html: str, edit_prompt: str, model: Optional[str] = None
) -> str:
    """기존 HTML을 편집 프롬프트에 맞춰 수정합니다.

    로깅: 민감한 본문은 전체를 남기지 않고 길이/프리뷰만 기록합니다.
    """
    logger.info(
        "Edit request (model=%s, prompt_len=%d, html_len=%d, prompt_preview='%s')",
        model or "default",
        len(edit_prompt or ""),
        len(original_html or ""),
        (edit_prompt or "")[:80],
    )
    try:
        llm = make_llm(model=model) if model else make_llm()
        chain = EDIT_PROMPT_TEMPLATE | llm
        resp = await chain.ainvoke(
            {"original_html": original_html, "edit_prompt": edit_prompt}
        )
        content = getattr(resp, "content", None)
        result = (content if content is not None else str(resp)).strip()
        if result:
            logger.info("Edit via LLM succeeded (out_len=%d)", len(result))
            return result
        else:
            logger.warning("LLM returned empty content; falling back to original")
    except Exception as e:
        logger.warning("Edit via LLM failed; falling back. Error: %s", e)

    # 폴백
    logger.info("Returning original HTML (fallback)")
    return original_html
