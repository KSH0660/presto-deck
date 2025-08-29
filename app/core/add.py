# app/core/add.py
import asyncio


async def add_slide_content(add_prompt: str) -> dict:
    """
    Generates content for a new slide based on a prompt.
    For now, it returns mock data.
    """
    # In a real implementation, this would call an LLM.
    await asyncio.sleep(0.01)  # Simulate async work
    return {
        "title": f"New Slide for: {add_prompt[:20]}...",
        "html_content": f"<h2>Content for {add_prompt}</h2><p>This is newly generated content.</p>",
    }
