"""
Mock LLM client for testing purposes.
"""

from typing import Dict, Any, Optional


class MockLLMClient:
    """Mock LLM client that returns fake responses."""

    async def generate_deck_plan(
        self,
        prompt: str,
        style_preferences: Optional[Dict[str, Any]] = None,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a mock deck plan."""
        return {
            "title": "Machine Learning Basics",
            "description": "An introduction to machine learning concepts",
            "target_audience": "Beginners",
            "estimated_duration": 30,
            "slides": [
                {
                    "order": 1,
                    "title": "Introduction to Machine Learning",
                    "content_outline": "Definition, types, and applications of ML",
                    "presenter_notes": "Start with simple examples",
                },
                {
                    "order": 2,
                    "title": "Supervised Learning",
                    "content_outline": "Classification and regression examples",
                    "presenter_notes": "Use visual examples",
                },
            ],
        }

    async def generate_slide_content(
        self,
        title: str,
        outline: str,
        context: Optional[str] = None,
    ) -> str:
        """Generate mock slide content."""
        return f"""
        <div class="slide">
            <h1>{title}</h1>
            <div class="content">
                <p>{outline}</p>
                <ul>
                    <li>Key point 1</li>
                    <li>Key point 2</li>
                    <li>Key point 3</li>
                </ul>
            </div>
        </div>
        """

    async def refine_slide_content(
        self,
        existing_content: str,
        feedback: str,
        context: Optional[str] = None,
    ) -> str:
        """Mock slide content refinement."""
        return existing_content + f"\n<!-- Refined based on: {feedback} -->"

    async def generate_presenter_notes(
        self,
        slide_title: str,
        slide_content: str,
        context: Optional[str] = None,
    ) -> str:
        """Generate mock presenter notes."""
        return f"Presenter notes for {slide_title}: Key talking points and transitions."
