# app/core/layout_selector.py
import asyncio
import logging
from typing import List

from langchain.schema.runnable import Runnable

from app.core.llm import make_llm
from app.core.prompts import SELECTOR_SYSTEM, SELECTOR_PROMPT
from app.core.template_manager import get_template_summaries
from app.models.schema import (
    InitialDeckPlan,
    SlideContent,
    SlideSpec,
    LayoutCandidates,
    DeckPlan,
)

logger = logging.getLogger(__name__)


def build_selector_chain(llm) -> Runnable:
    """단일 슬라이드에 대한 레이아웃 후보를 선택하는 LLM 체인을 빌드합니다."""
    return SELECTOR_PROMPT | llm.with_structured_output(LayoutCandidates)


async def select_layout_for_slide(
    slide_content: SlideContent,
    deck_plan: InitialDeckPlan,
    user_request: str,
    template_summaries_prompt: str,
    llm,
) -> SlideSpec:
    """단일 슬라이드 콘텐츠에 가장 적합한 레이아웃 후보들을 선택하여 완전한 SlideSpec을 반환합니다."""
    selector_chain = build_selector_chain(llm)

    slide_titles = "\n".join(f"- {s.title}" for s in deck_plan.slides)

    try:
        logger.debug(
            "Selecting layout for slide %d: %s", slide_content.slide_id, slide_content.title
        )
        selection: LayoutCandidates = await selector_chain.ainvoke(
            {
                "system": SELECTOR_SYSTEM,
                "user_request": user_request,
                "deck_topic": deck_plan.topic,
                "deck_audience": deck_plan.audience,
                "slide_titles": slide_titles,
                "current_slide_json": slide_content.model_dump_json(indent=2),
                "template_summaries": template_summaries_prompt,
            }
        )
        logger.debug(
            "Layout selected for slide %d: %s",
            slide_content.slide_id,
            selection.layout_candidates,
        )
        # SlideContent와 layout_candidates를 결합하여 SlideSpec 반환
        return SlideSpec(
            **slide_content.model_dump(),
            layout_candidates=selection.layout_candidates,
        )
    except Exception as e:
        logger.error(
            "Error during layout selection for slide %d: %s",
            slide_content.slide_id,
            e,
            exc_info=True,
        )
        # LLM 호출 실패 시 빈 리스트로 layout_candidates를 채워 SlideSpec 반환
        return SlideSpec(**slide_content.model_dump(), layout_candidates=[])


async def run_layout_selection_for_deck(
    initial_deck_plan: InitialDeckPlan, user_request: str, model: str
) -> DeckPlan:
    """
    덱 플랜의 모든 슬라이드에 대해 병렬적으로 레이아웃 후보를 선택하고,
    완성된 DeckPlan 객체를 생성하여 반환합니다.
    """
    logger.info(
        "Starting layout selection for %d slides.", len(initial_deck_plan.slides)
    )
    llm = make_llm(model=model)
    summaries = get_template_summaries()
    summaries_prompt = "\n".join(
        f"- {name}: {description}" for name, description in summaries.items()
    )

    tasks = [
        select_layout_for_slide(
            slide_content, initial_deck_plan, user_request, summaries_prompt, llm
        )
        for slide_content in initial_deck_plan.slides
    ]

    # List[SlideSpec]이 반환됨
    slide_specs: List[SlideSpec] = await asyncio.gather(*tasks)

    # 최종 DeckPlan 객체 생성
    final_deck_plan = DeckPlan(
        topic=initial_deck_plan.topic,
        audience=initial_deck_plan.audience,
        slides=slide_specs,
    )

    logger.info("Layout selection completed for all slides.")
    return final_deck_plan
