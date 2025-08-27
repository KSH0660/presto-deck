# app/core/slide_worker.py

import logging  # Added
from typing import Dict, List
from app.models.schema import SlideSpec, DeckPlan, SlideHTML
from app.core.content_writer import write_slide_content, subset_catalog_to_prompt

logger = logging.getLogger(__name__)  # Added


async def process_slide(
    slide_spec: SlideSpec,
    deck_plan: DeckPlan,
    candidate_template_names: List[str],
    template_catalog: Dict[str, str],
    model: str,
) -> SlideHTML:
    """한 슬라이드의 전체 처리과정을 담당하는 워커"""
    logger.info(
        "Processing slide %d: %s", slide_spec.slide_id, slide_spec.title
    )  # Added

    # 후보 템플릿 HTML을 프롬프트용으로 변환
    candidate_templates_html = subset_catalog_to_prompt(
        template_catalog, candidate_template_names
    )

    # 컨텐츠 생성
    rendered_slide = await write_slide_content(
        slide_spec=slide_spec,
        deck_plan=deck_plan,
        candidate_templates_html=candidate_templates_html,
        model=model,
    )

    logger.info(
        "Finished processing slide %d: %s", slide_spec.slide_id, slide_spec.title
    )  # Added
    return rendered_slide
