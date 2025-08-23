import os
import json
import re
from pathlib import Path

# BeautifulSoup is recommended for robust parsing, but using regex for simplicity here.
# from bs4 import BeautifulSoup

# --- CONFIGURATION ---
ASSET_DIR = Path("asset")
TEMPLATE_DIR = Path("presto/templates")
METADATA_FILE = TEMPLATE_DIR / "metadata.json"
SLIDE_SELECTORS = [".slide", ".slide-container"]


def get_slide_theme(file_path: Path) -> str:
    """Extracts a theme name from the file path (e.g., 'sample1')."""
    try:
        return file_path.parent.name
    except IndexError:
        return "general"


def get_structural_info(slide_html: str) -> dict:
    """Extracts basic structural information from slide HTML."""
    # In a real scenario, BeautifulSoup would be much more reliable.
    # soup = BeautifulSoup(slide_html, 'html.parser')
    # tags = [tag.name for tag in soup.find_all()]
    # return {tag: tags.count(tag) for tag in set(tags)}

    tags = re.findall(r"<([a-zA-Z0-9]+)", slide_html)
    return {tag: tags.count(tag) for tag in set(tags)}


def process_slide(
    slide_html: str,
    head_content: str,
    source_path: Path,
    slide_index: int,
    existing_metadata: dict,
) -> tuple[str, dict]:
    """Processes a single slide, saves it, and returns its metadata."""
    theme = get_slide_theme(source_path)
    template_id = f"{theme}_{source_path.stem}_{slide_index}"

    # --- Idempotency Check ---
    # If the template ID already exists in the metadata, skip processing.
    if template_id in existing_metadata:
        print(f"Skipping existing template ID: {template_id}")
        return None, None

    # Create a full, valid HTML document for the single slide
    final_html = f"<!DOCTYPE html>\n<html>\n<head>\n{head_content}\n</head>\n<body>\n{slide_html}\n</body>\n</html>"

    template_filename = f"{template_id}.html"
    template_path = TEMPLATE_DIR / template_filename

    print(f"Creating new template: {template_path}")
    template_path.write_text(final_html, encoding="utf-8")

    metadata = {
        "template_id": template_id,
        "source_file": str(source_path),
        "theme": theme,
        "description": "[AUTO-GENERATED] This needs to be enriched by an LLM.",
        "tags": [theme],
        "use_case": "[AUTO-GENERATED] This needs to be enriched by an LLM.",
        "structure": get_structural_info(slide_html),
        "template_path": str(template_path),
    }

    return template_id, metadata


def find_slides(html_content: str) -> list[str]:
    """Finds all slide containers in the HTML content."""
    all_slides = []
    for selector in SLIDE_SELECTORS:
        # This regex is very basic and might fail on complex, nested structures.
        # It looks for a div with a specific class.
        # A proper HTML parser would be far more robust.
        pattern = re.compile(
            f'<div class="{selector.strip(".")}".*?>.*?</div>', re.DOTALL
        )
        slides = pattern.findall(html_content)
        # A better approach to avoid nested divs of the same class:
        # We can find all start tags and then find the matching end tag.
        # This is still complex with regex. The current approach is a simplification.
        all_slides.extend(slides)

    # If no specific selectors found, take the whole body content
    if not all_slides:
        body_match = re.search(r"<body>(.*?)</body>", html_content, re.DOTALL)
        if body_match:
            return [body_match.group(1).strip()]
    return all_slides


def main():
    """Main function to build templates from assets."""
    print("--- Starting Template Build Process ---")

    if not ASSET_DIR.exists():
        print(f"Asset directory not found: {ASSET_DIR}")
        return

    TEMPLATE_DIR.mkdir(exist_ok=True)

    all_metadata = {}
    if METADATA_FILE.exists():
        try:
            all_metadata = json.loads(METADATA_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(
                f"Warning: Could not parse existing metadata file at {METADATA_FILE}. Starting fresh."
            )
            all_metadata = {}

    for root, _, files in os.walk(ASSET_DIR):
        for file in files:
            if file.endswith(".html"):
                source_path = Path(root) / file
                print(f"\nProcessing: {source_path}")

                html_content = source_path.read_text(encoding="utf-8")

                head_match = re.search(r"<head>(.*?)</head>", html_content, re.DOTALL)
                head_content = head_match.group(1) if head_match else ""

                slides = find_slides(html_content)

                if not slides:
                    print(f"Could not find any slide content in {source_path}")
                    continue

                print(f"Found {len(slides)} slide(s) in {source_path}")

                for i, slide_html in enumerate(slides):
                    template_id, metadata = process_slide(
                        slide_html, head_content, source_path, i, all_metadata
                    )
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
    main()
