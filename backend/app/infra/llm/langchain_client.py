"""
LangChain client for LLM integration.
"""

from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser


class LangChainClient:
    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ):
        self.llm = ChatOpenAI(
            model=model_name, temperature=temperature, max_tokens=max_tokens
        )
        self.parser = StrOutputParser()

    async def generate_text(
        self, prompt: str, system_message: Optional[str] = None
    ) -> str:
        """Generate text response from LLM."""
        messages = []

        if system_message:
            messages.append(SystemMessage(content=system_message))

        messages.append(HumanMessage(content=prompt))

        # Generate response
        response = await self.llm.ainvoke(messages)
        return self.parser.parse(response)

    async def generate_deck_plan(
        self, prompt: str, style_preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate structured deck plan from user prompt."""
        system_prompt = """
        You are an expert presentation designer. Create a comprehensive deck plan
        with clear slide structure, engaging content, and logical flow.

        Return a JSON object with this structure:
        {
            "title": "Presentation Title",
            "theme": "suggested theme based on content",
            "slides": [
                {
                    "title": "Slide Title",
                    "content": "Detailed content outline",
                    "notes": "Presenter notes and speaking points"
                }
            ]
        }

        Keep slides focused, limit to 15 slides maximum.
        Make content engaging and professional.
        """

        user_prompt = f"""
        Create a presentation deck plan for: {prompt}

        Style preferences: {style_preferences}

        Requirements:
        - Professional and engaging content
        - Clear narrative flow
        - Appropriate for business/educational context
        - Include practical examples where relevant
        """

        response = await self.generate_text(user_prompt, system_prompt)

        # Parse JSON response
        import json

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Fallback if LLM doesn't return valid JSON
            return {
                "title": "Generated Presentation",
                "theme": "professional",
                "slides": [
                    {
                        "title": "Introduction",
                        "content": response[:500] + "...",
                        "notes": "Generated content needs manual review",
                    }
                ],
            }

    async def generate_slide_html(
        self, title: str, content_outline: str, template_type: str, presenter_notes: str
    ) -> str:
        """Generate HTML content for a single slide."""
        system_prompt = f"""
        You are an expert web designer creating HTML content for presentation slides.
        Generate semantic, accessible HTML content using the {template_type} template style.

        Requirements:
        - Use semantic HTML5 elements (header, main, section, etc.)
        - Include appropriate CSS classes for styling
        - Make content visually engaging
        - No external scripts or unsafe content
        - Keep HTML clean and well-structured

        Return only the HTML content (no <html>, <head>, or <body> tags).
        """

        user_prompt = f"""
        Generate HTML content for this slide:

        Title: {title}
        Content Outline: {content_outline}
        Template Style: {template_type}
        Presenter Notes: {presenter_notes}

        Make the content professional, engaging, and visually appealing.
        Use bullet points, headings, and structure appropriately.
        """

        return await self.generate_text(user_prompt, system_prompt)
