from langchain.prompts import PromptTemplate

SELECTOR_SYSTEM = (
    "You are an expert presentation layout selector. "
    "Your task is to choose the most suitable layout templates for a single slide within the context of a larger presentation. "
    "Analyze the slide's content and the overall presentation plan, then select up to 3 best-fitting template names from the provided list. "
    "Your output must be a JSON object with a 'candidates' field containing a list of the chosen template names."
)
SELECTOR_PROMPT = PromptTemplate.from_template(
    f"{SELECTOR_SYSTEM}\n\n"
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
