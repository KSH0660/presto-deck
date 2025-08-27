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

# --- Step B: Select Layout for Individual Slide ---
SELECTOR_SYSTEM = (
    "You are an expert presentation layout selector. "
    "Your task is to choose the most suitable layout templates for a single slide within the context of a larger presentation. "
    "Analyze the slide's content and the overall presentation plan, then select up to 3 best-fitting template names from the provided list. "
    "Your output must be a JSON object with a 'candidates' field containing a list of the chosen template names."
)
SELECTOR_PROMPT = PromptTemplate.from_template(
    "{system}\n\n"
    "## Overall Presentation Context\n"
    "- User's Request: {user_request}\n"
    "- Presentation Topic: {deck_topic}\n"
    "- Target Audience: {deck_audience}\n"
    "- All Slide Titles in Order:\n{slide_titles}\n\n"
    "## Current Slide to Analyze\n"
    "```json\n{current_slide_json}\n```\n\n"
    "## Available Templates\n"
    "{template_summaries}\n\n"
    "## Your Task\n"
    "Based on all the information above, select up to 3 template names from the 'Available Templates' that would be the best fit for the 'Current Slide to Analyze'.\n"
    "Consider the slide's title, key points, and any data it might contain.\n"
    'Your output **must** be a JSON object with a single key "candidates", which is a list of strings (the template names).'
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

# --- Step C: Generate Template Summary ---
TEMPLATE_SUMMARY_SYSTEM = (
    "You are an expert in analyzing HTML presentation slide templates. "
    "Your task is to analyze the provided HTML code for a single slide and generate a concise, "
    "one-sentence summary of its structure and ideal use case."
)
TEMPLATE_SUMMARY_PROMPT = PromptTemplate.from_template(
    "{system}\n\n"
    "## HTML Content\n"
    "```html\n{html_content}\n```\n\n"
    "## Your Task\n"
    "Analyze the HTML content above. Describe its layout and the best type of content for it in a single, clear sentence. "
    'For example: "A standard title and content slide with a two-column layout for bullet points." '
    'or "A full-width cover image with a centered title, ideal for section breaks.'
)
