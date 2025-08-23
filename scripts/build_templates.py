import os
import json
import re
import asyncio
import sys
import uuid
import hashlib
from pathlib import Path
from pydantic import BaseModel, Field

# --- Add project root to sys.path for module imports ---
sys.path.append(str(Path(__file__).resolve().parent.parent))

from presto.app.core.llm_openai import generate_content_openai

# --- CONFIGURATION ---
ASSET_DIR = Path("asset")
TEMPLATE_DIR = Path("presto/templates")
METADATA_FILE = TEMPLATE_DIR / "metadata.json"
CACHE_FILE = TEMPLATE_DIR / ".template_cache.json"
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
    slide_html: str, head_content: str, source_path: Path, cache: dict
) -> tuple[str, dict, str] | None:
    """Processes a single slide, saves it, and returns its AI-enriched metadata."""
    content_hash = hashlib.sha256(slide_html.encode("utf-8")).hexdigest()

    if content_hash in cache:
        template_id = cache[content_hash]
        print(
            f"Skipping cached content (Hash: {content_hash[:7]}... -> ID: {template_id})"
        )
        return None

    template_id = uuid.uuid4().hex
    final_html = f"<!DOCTYPE html>\n<html>\n<head>\n{head_content}\n</head>\n<body>\n{slide_html}\n</body>\n</html>"
    template_filename = f"{template_id}.html"
    template_path = TEMPLATE_DIR / template_filename

    print(f"New content detected. Analyzing with LLM (Hash: {content_hash[:7]}...)")

    try:
        prompt = create_enrichment_prompt(slide_html)
        enriched_data = await generate_content_openai(
            prompt, response_model=EnrichedMetadata
        )
    except Exception as e:
        print(f"Error during LLM enrichment for new content: {e}")
        return None

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

    return template_id, metadata, content_hash


def find_slides(html_content: str) -> list[str]:
    """Finds all slide containers in the HTML content."""
    # This basic regex might not correctly handle complex nested divs.
    # For production, a proper HTML parser like BeautifulSoup is recommended.
    slides = re.findall(
        r"<div class=\"slide(?:-container)?\".*?>.*?</div>", html_content, re.DOTALL
    )
    if not slides:
        body_match = re.search(r"<body>(.*?)</body>", html_content, re.DOTALL)
        if body_match:
            return [body_match.group(1).strip()]
    return slides


async def main():
    """Main async function to build templates from assets."""
    print("--- Starting Smart Template Build Process (with Caching) ---")
    TEMPLATE_DIR.mkdir(exist_ok=True)

    # Load existing metadata and cache
    all_metadata = (
        json.loads(METADATA_FILE.read_text(encoding="utf-8"))
        if METADATA_FILE.exists()
        else {}
    )
    cache = (
        json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        if CACHE_FILE.exists()
        else {}
    )

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
                    continue

                print(f"\nProcessing {source_path}: Found {len(slides)} slide(s)")
                for slide_html in slides:
                    tasks.append(
                        process_slide(slide_html, head_content, source_path, cache)
                    )

    results = await asyncio.gather(*tasks)

    new_items_processed = 0
    for result in results:
        if result:
            new_items_processed += 1
            template_id, metadata, content_hash = result
            all_metadata[template_id] = metadata
            cache[content_hash] = template_id

    if new_items_processed > 0:
        print(f"\nProcessed {new_items_processed} new items.")
        METADATA_FILE.write_text(
            json.dumps(all_metadata, indent=4, ensure_ascii=False), encoding="utf-8"
        )
        CACHE_FILE.write_text(json.dumps(cache, indent=4), encoding="utf-8")
        print(f"Successfully updated {METADATA_FILE} and {CACHE_FILE}")
    else:
        print("\nNo new content found. All templates are up-to-date.")

    print("\n--- Template Build Process Finished ---")


if __name__ == "__main__":
    # Ensure .env is loaded for the OpenAI key
    from dotenv import load_dotenv

    load_dotenv()
    asyncio.run(main())
