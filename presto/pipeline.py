import os
import glob
import json
from typing import Dict, List

from langchain.schema.runnable import Runnable
from presto.llm import make_llm
from presto.models import DeckPlan, SlideHTML, LayoutSelection
from presto.prompt import (
    PLANNER_SYSTEM,
    PLANNER_PROMPT,
    SELECTOR_SYSTEM,
    SELECTOR_PROMPT,
    RENDER_SYSTEM,
    RENDER_PROMPT,
)

# -------- 템플릿 로더 / 프롬프트 변환 --------


def load_template_catalog(template_dir: str = "templates") -> Dict[str, str]:
    """
    templates/*.html => {파일명: 내용}. 폴더가 비어있으면 기본 2종 제공.
    """
    catalog: Dict[str, str] = {}
    if os.path.isdir(template_dir):
        for path in glob.glob(os.path.join(template_dir, "*.html")):
            name = os.path.basename(path)
            with open(path, "r", encoding="utf-8") as f:
                catalog[name] = f.read()

    return catalog


def catalog_to_prompt(catalog: Dict[str, str]) -> str:
    chunks = []
    for name, html in catalog.items():
        chunks.append(f"=== TEMPLATE: {name} ===\n{html}\n")
    return "\n".join(chunks)


def subset_catalog_to_prompt(catalog: Dict[str, str], names: List[str]) -> str:
    """선택된 템플릿들만 프롬프트 문자열로 변환."""
    chunks = []
    for name in names:
        html = catalog.get(name, "")
        if html:
            chunks.append(f"=== TEMPLATE: {name} ===\n{html}\n")
    return "\n".join(chunks)


# -------- 체인 빌더 --------


def build_planner_chain(llm) -> Runnable:
    """사용자 요청 → DeckPlan(Pydantic)"""
    return PLANNER_PROMPT | llm.with_structured_output(DeckPlan)


def build_selector_chain(llm) -> Runnable:
    """DeckPlan + 전체 템플릿 카탈로그 → 각 슬라이드별 후보 템플릿 목록(Pydantic)"""
    return SELECTOR_PROMPT | llm.with_structured_output(LayoutSelection)


def build_renderer_chain(llm) -> Runnable:
    """후보 템플릿(일부) + SlideSpec → SlideHTML(Pydantic)"""
    return RENDER_PROMPT | llm.with_structured_output(SlideHTML)


# -------- 실행 함수 --------


def run_pipeline(
    user_request: str, model: str = "gpt-4o-mini", max_concurrency: int = 12
):
    llm = make_llm(model=model)

    # 1) 전체 덱 기획
    plan_chain = build_planner_chain(llm)
    deck_plan: DeckPlan = plan_chain.invoke(
        {"system": PLANNER_SYSTEM, "user_request": user_request}
    )

    # 2) 후보 템플릿 선택 (전체 plan + 전체 카탈로그를 한 번만 입력)
    catalog = load_template_catalog("templates")
    selector_chain = build_selector_chain(llm)
    selection: LayoutSelection = selector_chain.invoke(
        {
            "system": SELECTOR_SYSTEM,
            "deck_plan_json": deck_plan.model_dump_json(indent=2),
            "template_catalog": catalog_to_prompt(catalog),
        }
    )

    # 슬라이드 ID -> 후보 템플릿 이름 리스트 매핑
    slide_to_candidates: Dict[int, List[str]] = {}
    for item in selection.items:
        slide_to_candidates[item.slide_id] = [c.template_name for c in item.candidates][
            :3
        ]  # 최대 3개

    # 3) 렌더링 (슬라이드별로 '후보 템플릿만' 전달)
    render_chain = build_renderer_chain(llm)

    inputs = []
    for slide in deck_plan.slides:
        cand_names = slide_to_candidates.get(slide.slide_id, [])
        candidate_templates = subset_catalog_to_prompt(catalog, cand_names)
        inputs.append(
            {
                "system": RENDER_SYSTEM,
                "candidate_templates": candidate_templates,
                "slide_json": json.dumps(slide.model_dump(), indent=2),
                "topic": deck_plan.topic,
                "audience": deck_plan.audience,
            }
        )

    rendered: List[SlideHTML] = render_chain.batch(
        inputs, config={"max_concurrency": max_concurrency}
    )
    return deck_plan, rendered


# -------- 로컬 테스트 --------
if __name__ == "__main__":
    req = (
        "Create an investor-focused deck for an 'AI-powered PPT auto-generation' product. "
        "Audience: seed/Series A VCs. Include problem, solution, product demo outline, "
        "TAM/SAM/SOM with reasonable numbers, GTM, competition & differentiation (Gamma/Tome/Canva), "
        "pricing, roadmap(6-12 months), and KPIs."
    )
    plan, slides = run_pipeline(req, model="gpt-4o-mini", max_concurrency=6)

    print("\n=== DECK PLAN ===")
    print(plan.model_dump_json(indent=2))

    print("\n=== RENDERED SLIDES ===")
    for s in slides:
        print(f"\n# Slide {s.slide_id} | Template: {s.template_name}\n{s.html}\n")
