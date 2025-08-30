from langchain.prompts import PromptTemplate

TEMPLATE_SUMMARY_SYSTEM = (
    "You are an expert in analyzing HTML presentation slide templates. "
    "Your task is to analyze the provided HTML code for a single slide and generate a concise, "
    "one-sentence summary of its structure and ideal use case."
)
TEMPLATE_SUMMARY_PROMPT = PromptTemplate.from_template(
    f"{TEMPLATE_SUMMARY_SYSTEM}\n\n"
    "## HTML Content\n"
    "```html\n{html_content}\n```\n\n"
    "## Your Task\n"
    "Analyze the HTML content above. Describe its layout and the best type of content for it in a single, clear sentence. "
    'For example: "A standard title and content slide with a two-column layout for bullet points." '
    'or "A full-width cover image with a centered title, ideal for section breaks."'
)
