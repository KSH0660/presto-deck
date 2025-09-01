import asyncio
import time
from typing import Any, Dict, Optional

import structlog
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.observability import metrics
from app.domain.exceptions import LLMException
from app.infrastructure.llm.models import DeckPlan, SlideContent
from app.infrastructure.llm.prompts import (
    DECK_PLAN_PROMPT,
    SLIDE_CONTENT_PROMPT,
    SLIDE_UPDATE_PROMPT,
)

logger = structlog.get_logger(__name__)


class LLMClient:
    def __init__(self) -> None:
        self.client: Optional[ChatOpenAI] = None
        self.max_retries = 3
        self.base_delay = 1.0

    async def initialize(self) -> None:
        """Initialize LangChain OpenAI client."""
        if not settings.openai_api_key:
            raise LLMException("OpenAI API key not configured")

        try:
            self.client = ChatOpenAI(
                api_key=settings.openai_api_key,
                model_name=settings.openai_model,
                temperature=settings.openai_temperature,
                max_tokens=settings.openai_max_tokens,
                max_retries=self.max_retries,
            )

            logger.info("LLM client initialized", model=settings.openai_model)

        except Exception as e:
            logger.error("Failed to initialize LLM client", error=str(e))
            raise LLMException(f"LLM client initialization failed: {e}")

    async def close(self) -> None:
        """Close LLM client connections."""
        # OpenAI client doesn't need explicit closing
        logger.info("LLM client closed")

    async def generate_deck_plan(
        self,
        title: str,
        topic: str,
        audience: Optional[str] = None,
        slide_count: int = 5,
        style: str = "professional",
        language: str = "en",
    ) -> DeckPlan:
        """Generate a deck plan using LLM with structured output."""
        start_time = time.time()

        try:
            if not self.client:
                raise LLMException("LLM client not initialized")

            # Create chain with structured output
            chain = DECK_PLAN_PROMPT | self.client.with_structured_output(DeckPlan)

            # Invoke with retry logic
            deck_plan = await self._invoke_chain_with_retry(
                chain,
                {
                    "title": title,
                    "topic": topic,
                    "audience": audience or "General audience",
                    "slide_count": slide_count,
                    "style": style,
                    "language": language,
                },
            )

            duration = time.time() - start_time

            # Record metrics (rough token estimation)
            prompt_text = f"{title} {topic} {audience or ''}"
            metrics.record_llm_usage(
                model=settings.openai_model,
                prompt_tokens=len(prompt_text) // 4,
                completion_tokens=100,  # Rough estimate for structured output
                duration=duration,
            )

            logger.info(
                "Deck plan generated",
                title=title,
                slide_count=deck_plan.total_slides,
                duration=f"{duration:.2f}s",
            )

            return deck_plan

        except Exception as e:
            logger.error("Failed to generate deck plan", error=str(e))
            raise LLMException(f"Deck plan generation failed: {e}")

    async def generate_slide_content(
        self,
        slide_info: Dict[str, Any],
        deck_context: Dict[str, Any],
        slide_number: int,
        include_speaker_notes: bool = True,
    ) -> SlideContent:
        """Generate content for a specific slide with structured output."""
        start_time = time.time()

        try:
            if not self.client:
                raise LLMException("LLM client not initialized")

            # Create chain with structured output
            chain = SLIDE_CONTENT_PROMPT | self.client.with_structured_output(
                SlideContent
            )

            # Invoke with retry logic
            slide_content = await self._invoke_chain_with_retry(
                chain,
                {
                    "deck_title": deck_context.get("title", "Unknown"),
                    "deck_topic": deck_context.get("topic", "Unknown"),
                    "deck_audience": deck_context.get("audience", "General"),
                    "slide_number": slide_number,
                    "slide_title": slide_info.get("title", "Unknown"),
                    "slide_type": slide_info.get("type", "content"),
                    "key_points": ", ".join(slide_info.get("key_points", [])),
                    "content_type": slide_info.get("content_type", "text"),
                    "notes_detail": "detailed" if include_speaker_notes else "minimal",
                },
            )

            duration = time.time() - start_time

            # Record metrics
            prompt_text = f"{slide_info.get('title', '')} {' '.join(slide_info.get('key_points', []))}"
            metrics.record_llm_usage(
                model=settings.openai_model,
                prompt_tokens=len(prompt_text) // 4,
                completion_tokens=150,  # Rough estimate for slide content
                duration=duration,
            )

            logger.info(
                "Slide content generated",
                slide_number=slide_number,
                title=slide_content.title,
                duration=f"{duration:.2f}s",
            )

            return slide_content

        except Exception as e:
            logger.error(
                "Failed to generate slide content",
                slide_number=slide_number,
                error=str(e),
            )
            raise LLMException(f"Slide content generation failed: {e}")

    async def update_slide_content(
        self, current_content: str, update_prompt: str, slide_context: Dict[str, Any]
    ) -> SlideContent:
        """Update existing slide content based on user prompt with structured output."""
        start_time = time.time()

        try:
            if not self.client:
                raise LLMException("LLM client not initialized")

            # Create chain with structured output
            chain = SLIDE_UPDATE_PROMPT | self.client.with_structured_output(
                SlideContent
            )

            # Invoke with retry logic
            slide_content = await self._invoke_chain_with_retry(
                chain,
                {
                    "current_content": current_content,
                    "update_prompt": update_prompt,
                    "slide_context": str(slide_context),
                },
            )

            duration = time.time() - start_time

            # Record metrics
            prompt_text = f"{current_content[:100]} {update_prompt}"
            metrics.record_llm_usage(
                model=settings.openai_model,
                prompt_tokens=len(prompt_text) // 4,
                completion_tokens=150,  # Rough estimate for updated content
                duration=duration,
            )

            logger.info("Slide content updated", duration=f"{duration:.2f}s")

            return slide_content

        except Exception as e:
            logger.error("Failed to update slide content", error=str(e))
            raise LLMException(f"Slide content update failed: {e}")

    async def _invoke_chain_with_retry(self, chain, input_data: Dict[str, Any]) -> Any:
        """Invoke LangChain chain with exponential backoff retry."""
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                return await chain.ainvoke(input_data)

            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2**attempt)
                    logger.warning(
                        "Chain invocation failed, retrying",
                        attempt=attempt + 1,
                        delay=delay,
                        error=str(e),
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "All chain invocation retry attempts failed", error=str(e)
                    )

        raise LLMException(
            f"Chain invocation failed after {self.max_retries} attempts: {last_exception}"
        )
