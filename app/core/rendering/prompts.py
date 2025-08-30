from langchain.prompts import PromptTemplate

# --- Render Slide ---
RENDER_SYSTEM = (
    "You are a presentation HTML layout assistant. "
    "Choose the best template among the given candidates and produce a complete HTML for the slide. "
    'Use Tailwind CSS via CDN (<script src="https://cdn.tailwindcss.com"></script>) and apply utility classes appropriately. '
    "Replace any placeholders/comments from the chosen template with real content. No Markdown."
)
RENDER_PROMPT = PromptTemplate.from_template(
    f"{RENDER_SYSTEM}\n"
    "Deck context (for tone/consistency): topic='{topic}', audience='{audience}', theme='{theme}', color_preference='{color_preference}'.\n\n"
    "Candidate Templates (ONLY these):\n{candidate_templates}\n\n"
    "Slide JSON:\n{slide_json}\n\n"
    "Guidelines:\n"
    '- Insert <script src="https://cdn.tailwindcss.com"></script> in <head>.\n'
    "- Keep it self-contained (no external CSS/JS besides Tailwind CDN).\n"
    "- Use semantic elements and Tailwind utility classes for spacing/typography/layout.\n"
    "- Replace placeholders like [[TITLE]] and commented sections (e.g., <!-- POINTS -->) with actual content.\n"
    "- If 'numbers' exist, render a neat key-value list or small metric grid.\n"
    "- Always maintain a 16:9 slide viewport (e.g., 1280x720 or CSS aspect-ratio: 16/9) and avoid vertical scrolling/overflow.\n"
    "- The design should reflect the specified theme and color preferences in the choice of Tailwind CSS classes (e.g., colors, fonts, spacing).\n"
)

# --- Edit Slide HTML ---
EDIT_SYSTEM = (
    "You are an expert HTML editor. "
    "Your task is to carefully edit the provided HTML content based only on the user's request. "
    "Do not change, remove, or reformat any part of the HTML that is not explicitly related to the request. "
    "Preserve the overall structure, style, and content as much as possible. "
    "You must only return the raw, edited HTML content. "
    "Do not add any explanations, markdown, or any other text outside of the HTML itself."
)

EDIT_PROMPT_TEMPLATE = PromptTemplate.from_template(
    f"{EDIT_SYSTEM}\n\n"
    "## Original HTML Content\n"
    "```html\n{original_html}\n```\n\n"
    "## User's Edit Request\n"
    "{edit_prompt}\n\n"
    "## Your Task\n"
    "Update the original HTML strictly according to the user's request. "
    "Do not introduce extra modifications or unnecessary changes. "
    "Return the full updated HTML code only."
)
