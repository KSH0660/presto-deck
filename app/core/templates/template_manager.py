# app/core/template_manager.py
import asyncio
import json
import os
import glob
from typing import Dict, Optional

from app.core.infra.config import settings
from app.core.providers.llm import make_llm
from app.core.templates.prompts import TEMPLATE_SUMMARY_PROMPT
from app.models.schema import TemplateSummary

# 전역 변수로 템플릿 요약 및 원본 HTML 캐시
TEMPLATE_SUMMARY_CATALOG: Dict[str, str] = {}
TEMPLATE_HTML_CATALOG: Dict[str, str] = {}


async def _generate_summary_for_template(
    html_content: str, model: str
) -> Optional[str]:
    """LLM을 사용하여 단일 HTML 템플릿의 요약을 생성합니다. 실패 시 None을 반환합니다."""
    llm = make_llm(model=model)
    chain = TEMPLATE_SUMMARY_PROMPT | llm.with_structured_output(TemplateSummary)
    try:
        result = await chain.ainvoke({"html_content": html_content})
        return result.summary
    except Exception as e:
        print(f"Error generating template summary: {e}")
        return None


async def initialize_template_data(template_dir: str = "app/templates"):
    """
    서버 시작 시 템플릿 데이터(HTML 원본, 요약)를 로드, 생성 및 캐시합니다.
    """
    global TEMPLATE_SUMMARY_CATALOG, TEMPLATE_HTML_CATALOG
    catalog_path = os.path.join(template_dir, "catalog.json")
    summary_catalog: Dict[str, str] = {}
    needs_update = False
    model = settings.DEFAULT_MODEL

    if os.path.exists(catalog_path):
        with open(catalog_path, "r", encoding="utf-8") as f:
            summary_catalog = json.load(f)

    current_templates = {
        os.path.basename(p): p for p in glob.glob(os.path.join(template_dir, "*.html"))
    }

    templates_to_generate = {}
    for name, path in current_templates.items():
        with open(path, "r", encoding="utf-8") as f:
            html_content = f.read()
            TEMPLATE_HTML_CATALOG[name] = html_content
            if name not in summary_catalog:
                templates_to_generate[name] = html_content

    if templates_to_generate:
        tasks = [
            _generate_summary_for_template(html, model)
            for html in templates_to_generate.values()
        ]
        new_summaries = await asyncio.gather(*tasks)

        for name, summary in zip(templates_to_generate.keys(), new_summaries):
            # 성공적으로 요약이 생성된 경우에만 추가
            if summary:
                summary_catalog[name] = summary
                needs_update = True

    TEMPLATE_SUMMARY_CATALOG = summary_catalog

    if needs_update:
        with open(catalog_path, "w", encoding="utf-8") as f:
            json.dump(summary_catalog, f, indent=2, ensure_ascii=False)
        print(f"Template catalog updated at {catalog_path}")
    else:
        print("Template catalog is up to date.")


def get_template_summaries() -> Dict[str, str]:
    """캐시된 템플릿 요약 카탈로그를 반환합니다."""
    return TEMPLATE_SUMMARY_CATALOG


def get_template_html_catalog() -> Dict[str, str]:
    """캐시된 템플릿 HTML 원본 카탈로그를 반환합니다."""
    return TEMPLATE_HTML_CATALOG
