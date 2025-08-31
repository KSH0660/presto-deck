# app/core/rendering/content_writer.py

from typing import Dict, List
import logging

from langchain.schema.runnable import Runnable
from app.core.providers.llm import make_llm
from app.models.schema import SlideSpec, SlideHTML, DeckPlan, GenerateRequest
from app.core.rendering.prompts import RENDER_PROMPT
from app.core.infra.llm_callbacks import PrometheusLLMCallback

logger = logging.getLogger(__name__)


def subset_catalog_to_prompt(catalog: Dict[str, str], names: List[str]) -> str:
    """선택된 템플릿들만 프롬프트 문자열로 변환."""
    chunks = []
    for name in names:
        html = catalog.get(name, "")
        if html:
            chunks.append(f"=== TEMPLATE: {name} ===\n{html}\n")
    return "\n".join(chunks)


def build_renderer_chain(llm) -> Runnable:
    """후보 템플릿(일부) + SlideSpec -> SlideHTML(Pydantic)"""
    return RENDER_PROMPT | llm.with_structured_output(SlideHTML)


async def write_slide_content(
    slide_spec: SlideSpec,
    deck_plan: DeckPlan,
    req: GenerateRequest,
    candidate_templates_html: str,
    model: str,
) -> SlideHTML:
    """슬라이드 명세와 후보 템플릿을 기반으로 최종 HTML 컨텐츠를 생성합니다."""
    llm = make_llm(model=model)
    renderer_chain = build_renderer_chain(llm)

    # 요청값 우선, 없으면 덱 기획에서 제안한 테마/컬러를 사용
    theme = req.theme or deck_plan.theme or "Not specified"
    color_pref = req.color_preference or deck_plan.color_preference or "Not specified"

    logger.info(
        "Rendering slide %d with theme='%s' | colors='%s'",
        slide_spec.slide_id,
        theme,
        color_pref,
    )

    rendered_slide: SlideHTML = await renderer_chain.ainvoke(
        {
            "candidate_templates": candidate_templates_html,
            "slide_json": slide_spec.model_dump_json(indent=2),
            "topic": deck_plan.topic,
            "audience": deck_plan.audience,
            "theme": theme,
            "color_preference": color_pref,
        },
        config={"callbacks": [PrometheusLLMCallback("render")]},
    )
    return rendered_slide
