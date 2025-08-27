# app/core/layout_selector.py
import asyncio
from typing import List

from langchain.schema.runnable import Runnable

from app.core.llm import make_llm
from app.core.prompts import SELECTOR_SYSTEM, SELECTOR_PROMPT
from app.core.template_manager import get_template_summaries
from app.models.schema import DeckPlan, SlideSpec, LayoutCandidates


def build_selector_chain(llm) -> Runnable:
    """단일 슬라이드에 대한 레이아웃 후보를 선택하는 LLM 체인을 빌드합니다."""
    return SELECTOR_PROMPT | llm.with_structured_output(LayoutCandidates)


async def select_layout_for_slide(
    slide: SlideSpec,
    deck_plan: DeckPlan,
    user_request: str,
    template_summaries_prompt: str,
    llm,
) -> List[str]:
    """단일 슬라이드에 가장 적합한 레이아웃 후보들을 선택합니다."""
    selector_chain = build_selector_chain(llm)

    slide_titles = "\n".join(f"- {s.title}" for s in deck_plan.slides)

    try:
        selection: LayoutCandidates = await selector_chain.ainvoke(
            {
                "system": SELECTOR_SYSTEM,
                "user_request": user_request,
                "deck_topic": deck_plan.topic,
                "deck_audience": deck_plan.audience,
                "slide_titles": slide_titles,
                "current_slide_json": slide.model_dump_json(indent=2),
                "template_summaries": template_summaries_prompt,
            }
        )
        return selection.candidates
    except Exception as e:
        print(f"Error during layout selection for slide {slide.slide_id}: {e}")
        # LLM 호출 실패 시 빈 리스트 반환 또는 기본값 사용
        return []


async def run_layout_selection_for_deck(
    deck_plan: DeckPlan, user_request: str, model: str
) -> DeckPlan:
    """
    덱 플랜의 모든 슬라이드에 대해 병렬적으로 레이아웃 후보를 선택하고,
    결과를 DeckPlan 객체에 업데이트하여 반환합니다.
    """
    llm = make_llm(model=model)
    summaries = get_template_summaries()
    summaries_prompt = "\n".join(
        f"- {name}: {description}" for name, description in summaries.items()
    )

    tasks = [
        select_layout_for_slide(slide, deck_plan, user_request, summaries_prompt, llm)
        for slide in deck_plan.slides
    ]

    results: List[List[str]] = await asyncio.gather(*tasks)

    for slide, candidates in zip(deck_plan.slides, results):
        slide.layout_candidates = candidates

    return deck_plan
