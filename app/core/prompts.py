from langchain.prompts import PromptTemplate

# --- Step A: 전체 덱 기획(DeckPlan) ---
PLANNER_SYSTEM = (
    "You are an expert presentation planner. "
    "Return a JSON object for a PPT plan following the provided schema. "
    "Include realistic numbers where relevant (can be estimates) and clear, concise slide bullets."
)
PLANNER_PROMPT = PromptTemplate.from_template(
    "{system}\n"
    "User request:\n{user_request}\n\n"
    "Rules:\n"
    "- 8~12 slides typical (adjust if user implies different).\n"
    "- Each slide must have: title, 3-6 key_points, numbers (if applicable), optional notes, optional section.\n"
    "- Audience-aware tone.\n"
    "- Output must be a JSON object that matches the target schema.\n"
)

# --- Step A': 후보 템플릿 선택 (DeckPlan + 템플릿 카탈로그 -> 각 슬라이드별 후보 템플릿) ---
SELECTOR_SYSTEM = (
    "You are a presentation layout selector. "
    "Given the whole deck plan and the available HTML templates, choose 1~3 best templates per slide, "
    "with brief reasoning. Focus on structure fit (bullets, two-column, metrics area, etc.)."
)
SELECTOR_PROMPT = PromptTemplate.from_template(
    "{system}\n"
    "Deck Plan (JSON):\n{deck_plan_json}\n\n"
    "Available Templates:\n{template_catalog}\n\n"
    "Instructions:\n"
    "- For each slide_id, suggest 1~3 template_name as candidates.\n"
    "- Provide very short reasons.\n"
)

# --- Step B: 렌더링 (후보 템플릿만 프롬프트에 포함) ---
# NOTE: JSON 강제 문구는 제거. Tailwind CDN 사용을 지시.
RENDER_SYSTEM = (
    "You are a presentation HTML layout assistant. "
    "Choose the best template among the given candidates and produce a complete HTML for the slide. "
    'Use Tailwind CSS via CDN (<script src="https://cdn.tailwindcss.com"></script>) and apply utility classes appropriately. '
    "Replace any placeholders/comments from the chosen template with real content. No Markdown."
)
RENDER_PROMPT = PromptTemplate.from_template(
    "{system}\n"
    "Deck context (for tone/consistency): topic='{topic}', audience='{audience}'.\n\n"
    "Candidate Templates (ONLY these):\n{candidate_templates}\n\n"
    "Slide JSON:\n{slide_json}\n\n"
    "Guidelines:\n"
    '- Insert <script src="https://cdn.tailwindcss.com"></script> in <head>.\n'
    "- Keep it self-contained (no external CSS/JS besides Tailwind CDN).\n"
    "- Use semantic elements and Tailwind utility classes for spacing/typography/layout.\n"
    "- Replace placeholders like [[TITLE]] and commented sections (e.g., <!-- POINTS -->) with actual content.\n"
    "- If 'numbers' exist, render a neat key-value list or small metric grid.\n"
)
