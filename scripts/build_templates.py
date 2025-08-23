import os
import json
import re
import asyncio
import sys
from pathlib import Path
from pydantic import BaseModel, Field

# --- Add project root to sys.path for module imports ---
sys.path.append(str(Path(__file__).resolve().parent.parent))

from presto.app.core.llm_openai import generate_content_openai

# --- CONFIGURATION ---
ASSET_DIR = Path("asset")
TEMPLATE_DIR = Path("presto/templates")
METADATA_FILE = TEMPLATE_DIR / "metadata.json"
SLIDE_SELECTORS = [".slide", ".slide-container"]


# --- Pydantic Model for LLM Response ---
class EnrichedMetadata(BaseModel):
    theme: str = Field(
        description="이 슬라이드 디자인의 전체적인 테마 (예: 'Modern Business', 'Pastel Infographic')"
    )
    description: str = Field(
        description="슬라이드의 디자인, 레이아웃, 목적을 설명하는 2-3문장의 한국어 설명"
    )
    tags: list[str] = Field(
        description="검색에 용이하도록 슬라이드의 특징을 나타내는 3-5개의 한국어 키워드 태그"
    )
    use_case: str = Field(
        description="이 슬라이드 템플릿이 가장 효과적으로 사용될 수 있는 구체적인 사용 사례를 한국어로 설명"
    )


def create_enrichment_prompt(slide_html: str) -> str:
    """Creates a prompt for the LLM to enrich metadata."""
    return f"""
    당신은 전문 프레젠테이션 디자이너입니다. 아래 제공되는 슬라이드의 HTML 코드를 분석하여, 이 슬라이드의 디자인적 특징과 가장 적합한 사용 사례를 파악해주세요.

    결과는 반드시 지정된 JSON 형식으로 한국어로 응답해야 합니다.

    - theme: 슬라이드의 전체적인 디자인 테마 (예: '모던 비즈니스', '파스텔 인포그래픽')
    - description: 슬라이드의 디자인, 레이아웃, 목적을 설명하는 2-3문장의 설명
    - tags: 검색에 용이하도록 슬라이드의 특징을 나타내는 3-5개의 키워드 태그
    - use_case: 이 템플릿이 가장 효과적으로 사용될 수 있는 구체적인 사용 사례

    --- 슬라이드 HTML 코드 ---
    {slide_html}
    --- END ---
    """


def get_structural_info(slide_html: str) -> dict:
    """Extracts basic structural information from slide HTML."""
    tags = re.findall(r"<([a-zA-Z0-9]+)", slide_html)
    return {tag: tags.count(tag) for tag in set(tags)}


async def process_slide(
    slide_html: str,
    head_content: str,
    source_path: Path,
    slide_index: int,
    existing_metadata: dict,
) -> tuple[str, dict]:
    """Processes a single slide, saves it, and returns its AI-enriched metadata."""
    theme_source = source_path.parent.name
    template_id = f"{theme_source}_{source_path.stem}_{slide_index}"

    if template_id in existing_metadata:
        print(f"Skipping existing template ID: {template_id}")
        return None, None

    final_html = f"<!DOCTYPE html>\n<html>\n<head>\n{head_content}\n</head>\n<body>\n{slide_html}\n</body>\n</html>"
    template_filename = f"{template_id}.html"
    template_path = TEMPLATE_DIR / template_filename

    print(f"Analyzing with LLM and creating new template: {template_path}")

    try:
        prompt = create_enrichment_prompt(slide_html)
        enriched_data = await generate_content_openai(
            prompt, response_model=EnrichedMetadata
        )
    except Exception as e:
        print(f"Error during LLM enrichment for {template_id}: {e}")
        return None, None

    template_path.write_text(final_html, encoding="utf-8")

    metadata = {
        "template_id": template_id,
        "source_file": str(source_path),
        "theme": enriched_data.theme,
        "description": enriched_data.description,
        "tags": enriched_data.tags,
        "use_case": enriched_data.use_case,
        "structure": get_structural_info(slide_html),
        "template_path": str(template_path),
    }

    return template_id, metadata


def find_slides(html_content: str) -> list[str]:
    """Finds all slide containers in the HTML content."""
    # This basic regex might not correctly handle complex nested divs.
    # For production, a proper HTML parser like BeautifulSoup is recommended.
    slides = re.findall(
        r'<div class="slide(?:-container)?".*?>.*?</div>', html_content, re.DOTALL
    )
    if not slides:
        body_match = re.search(r"<body>(.*?)</body>", html_content, re.DOTALL)
        if body_match:
            return [body_match.group(1).strip()]
    return slides


async def main():
    """Main async function to build templates from assets."""
    print("--- Starting AI-Powered Template Build Process ---")

    if not ASSET_DIR.exists():
        print(f"Asset directory not found: {ASSET_DIR}")
        return

    TEMPLATE_DIR.mkdir(exist_ok=True)

    all_metadata = {}
    if METADATA_FILE.exists():
        try:
            all_metadata = json.loads(METADATA_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"Warning: Could not parse {METADATA_FILE}. Starting fresh.")
            all_metadata = {}

    tasks = []
    for root, _, files in os.walk(ASSET_DIR):
        for file in files:
            if file.endswith(".html"):
                source_path = Path(root) / file
                html_content = source_path.read_text(encoding="utf-8")
                head_content = (
                    re.search(r"<head>(.*?)</head>", html_content, re.DOTALL).group(1)
                    if re.search(r"<head>(.*?)</head>", html_content, re.DOTALL)
                    else ""
                )
                slides = find_slides(html_content)

                if not slides:
                    print(f"Could not find any slide content in {source_path}")
                    continue

                print(f"\nProcessing {source_path}: Found {len(slides)} slide(s)")
                for i, slide_html in enumerate(slides):
                    task = process_slide(
                        slide_html, head_content, source_path, i, all_metadata
                    )
                    tasks.append(task)

    results = await asyncio.gather(*tasks)

    for template_id, metadata in results:
        if template_id and metadata:
            all_metadata[template_id] = metadata

    if all_metadata:
        print(
            f"\nWriting metadata for {len(all_metadata)} templates to {METADATA_FILE}"
        )
        METADATA_FILE.write_text(
            json.dumps(all_metadata, indent=4, ensure_ascii=False), encoding="utf-8"
        )

    print("\n--- Template Build Process Finished ---")


if __name__ == "__main__":
    # Ensure .env is loaded for the OpenAI key
    from dotenv import load_dotenv

    load_dotenv()
    asyncio.run(main())
