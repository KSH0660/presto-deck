# app/core/layout_selector.py

import os
import glob
from typing import Dict
from langchain.schema.runnable import Runnable
from app.core.llm import make_llm
from app.models.schema import DeckPlan, LayoutSelection
from app.core.prompts import SELECTOR_SYSTEM, SELECTOR_PROMPT


def load_template_catalog(template_dir: str = "app/templates") -> Dict[str, str]:
    """
    templates/*.html => {파일명: 내용}.
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


def build_selector_chain(llm) -> Runnable:
    """DeckPlan + 전체 템플릿 카탈로그 -> 각 슬라이드별 후보 템플릿 목록(Pydantic)"""
    return SELECTOR_PROMPT | llm.with_structured_output(LayoutSelection)


async def select_layouts(deck_plan: DeckPlan, model: str) -> LayoutSelection:
    """덱 플랜에 가장 적합한 레이아웃 후보들을 선택합니다."""
    llm = make_llm(model=model)
    catalog = load_template_catalog()
    selector_chain = build_selector_chain(llm)
    selection: LayoutSelection = await selector_chain.ainvoke(
        {
            "system": SELECTOR_SYSTEM,
            "deck_plan_json": deck_plan.model_dump_json(indent=2),
            "template_catalog": catalog_to_prompt(catalog),
        }
    )
    return selection
