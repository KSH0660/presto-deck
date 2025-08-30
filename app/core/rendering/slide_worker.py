# app/core/rendering/slide_worker.py

import logging
from typing import Dict
from app.models.schema import SlideSpec, DeckPlan, SlideHTML, GenerateRequest
from app.core.rendering.content_writer import (
    write_slide_content,
    subset_catalog_to_prompt,
)

logger = logging.getLogger(__name__)


async def process_slide(
    slide_spec: SlideSpec,
    deck_plan: DeckPlan,
    req: GenerateRequest,
    template_catalog: Dict[str, str],
    model: str,
) -> SlideHTML:
    """한 슬라이드의 전체 처리과정을 담당하는 워커"""
    logger.info("Processing slide %d: %s", slide_spec.slide_id, slide_spec.title)

    candidate_names = slide_spec.layout_candidates or []
    candidate_templates_html = subset_catalog_to_prompt(
        template_catalog, candidate_names
    )

    rendered_slide = await write_slide_content(
        slide_spec=slide_spec,
        deck_plan=deck_plan,
        req=req,
        candidate_templates_html=candidate_templates_html,
        model=model,
    )

    logger.info(
        "Finished processing slide %d: %s", slide_spec.slide_id, slide_spec.title
    )
    return rendered_slide
