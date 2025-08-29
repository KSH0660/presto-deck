# app/core/edit.py
import logging
from app.core.llm import make_llm
from app.core.prompts import EDIT_PROMPT_TEMPLATE
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)


async def edit_slide_content(original_html: str, edit_prompt: str) -> str:
    """
    Edits the HTML content of a slide based on a prompt using an LLM.

    Args:
        original_html: The original HTML content of the slide.
        edit_prompt: The user's prompt describing the desired edits.

    Returns:
        The edited HTML content as a string.
    """
    logger.info("Invoking LLM to edit slide content.")
    logger.debug(
        f"Original HTML length: {len(original_html)}, Edit prompt: '{edit_prompt}'"
    )

    llm = make_llm()
    chain = EDIT_PROMPT_TEMPLATE | llm | StrOutputParser()

    new_html = await chain.ainvoke(
        {
            "original_html": original_html,
            "edit_prompt": edit_prompt,
        }
    )

    logger.info("Successfully received edited HTML from LLM.")
    logger.debug(f"New HTML length: {len(new_html)}")

    return new_html
