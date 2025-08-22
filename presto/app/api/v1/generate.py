import json
import os
from fastapi import APIRouter, HTTPException
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from presto.app.models.presentation import PresentationRequest, PresentationResponse
from presto.app.core.llm_openai import generate_content_openai

router = APIRouter()

# --- Jinja2 Template Setup ---
TEMPLATE_DIR = os.path.join("presto", "templates")
template_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

def get_available_layouts(theme: str) -> list[str]:
    """Scans the file system to get available layout names for a given theme."""
    try:
        theme_dir = os.path.join(TEMPLATE_DIR, theme)
        if not os.path.isdir(theme_dir):
            return []
        # Return names without the .html extension
        return [f.replace(".html", "") for f in os.listdir(theme_dir) if f.endswith(".html")]
    except Exception:
        return [] # Return empty list on any error

# --- AI Prompt ---
PLAN_PROMPT_TEMPLATE = """
You are an Expert Presentation Strategist.
Your goal is to create a logical presentation plan and structure it for a templating engine.

**Topic:** "{topic}"
**Number of Slides:** {slide_count}

**Instructions:**
1.  **Review Available Layouts:** Here are the layouts you MUST choose from for this theme:
    `{layouts}`
2.  **Create a Narrative Arc:** The presentation must have a clear beginning, middle, and end.
3.  **Select Layout:** For each slide, you MUST choose the most appropriate layout from the provided list.
4.  **Generate Content:** Provide a `title` and a `content` list for each slide.
5.  **JSON Output:** Your response **MUST** be a single, valid JSON object. Do not include any text or markdown formatting. The structure is:

    ```json
    {{
      "title": "The Main Presentation Title",
      "slides": [
        {{
          "layout": "title",
          "title": "The Title of the First Slide",
          "content": ["A short, engaging subtitle"]
        }},
        {{
          "layout": "list",
          "title": "A Section Title",
          "content": ["Bullet point 1", "Bullet point 2", "Bullet point 3"]
        }}
      ]
    }}
    ```
"""

@router.post("/generate", response_model=PresentationResponse)
async def generate_presentation(request: PresentationRequest):
    """
    Creates a new presentation by:
    1. Dynamically finding available layouts for the selected theme.
    2. Calling an AI to generate a structured plan with content and layout choices.
    3. Using a templating engine (Jinja2) to render the final HTML from template files.
    """
    try:
        # 1. Get available layouts for the chosen theme
        available_layouts = get_available_layouts(request.theme)
        if not available_layouts:
            raise HTTPException(status_code=404, detail=f"Theme '{request.theme}' not found or has no layouts.")

        # 2. Generate the presentation plan from the AI
        plan_prompt = PLAN_PROMPT_TEMPLATE.format(
            topic=request.topic,
            slide_count=request.slide_count,
            layouts=available_layouts
        )
        plan_response_str = await generate_content_openai(plan_prompt, model=request.model)
        plan_data = json.loads(plan_response_str)
        slides_plan = plan_data.get("slides", [])

        # 3. Render HTML from templates
        slides_html = []
        for slide in slides_plan:
            layout = slide.get("layout", "list")
            template_name = f"{request.theme}/{layout}.html"
            
            try:
                template = template_env.get_template(template_name)
                rendered_html = template.render(slide) # Pass the whole slide dict as context
                slides_html.append(rendered_html)
            except TemplateNotFound:
                slides_html.append(f"<div><h2>Error</h2><p>Layout '{layout}' not found for theme '{request.theme}'.</p></div>")

        return PresentationResponse(
            title=plan_data.get("title", request.topic),
            slides_html=slides_html,
            plan=plan_data
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to decode the presentation plan from the AI model.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
