"""
Pure infrastructure LLM client for LangChain integration.

This client provides only the basic invoke functionality without any domain knowledge.
Prompts and structured output definitions should be handled in the Use Case layer.
"""

from typing import List, Optional, Type, TypeVar, Union
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel
from app.infra.config.logging_config import get_logger
from app.application.ports import LLMServicePort

T = TypeVar("T", bound=BaseModel)


class LangChainClient(LLMServicePort):
    """
    Infrastructure-layer LLM client providing pure invoke functionality.

    No domain knowledge or prompts should be included here.
    All business logic belongs in the Use Case layer.
    """

    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.3,
        max_tokens: int = 4000,
        base_url: Optional[str] = None,
        **kwargs,
    ):
        """Initialize LangChain client with LLM configuration."""
        llm_kwargs = {
            "model": model_name,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        # Add base_url if provided (for OpenAI-compatible servers)
        if base_url:
            llm_kwargs["base_url"] = base_url

        self.llm = ChatOpenAI(**llm_kwargs)
        self._text_parser = StrOutputParser()
        self._log = get_logger("infra.llm")

    async def invoke_text(self, messages: List[BaseMessage]) -> str:
        """
        Invoke LLM with messages and return text response.

        Args:
            messages: List of LangChain message objects

        Returns:
            Raw text response from LLM
        """
        response = await self.llm.ainvoke(messages)
        self._log.info("llm.invoke.text")
        return self._text_parser.parse(response)

    async def invoke_structured(
        self, messages: List[BaseMessage], response_model: Type[T]
    ) -> T:
        """
        Invoke LLM with structured output using Pydantic model.

        Args:
            messages: List of LangChain message objects
            response_model: Pydantic model class for structured output

        Returns:
            Parsed Pydantic model instance
        """
        structured_llm = self.llm.with_structured_output(response_model)
        response = await structured_llm.ainvoke(messages)
        self._log.info("llm.invoke.structured", model=response_model.__name__)
        return response

    async def invoke_with_retry(
        self,
        messages: List[BaseMessage],
        response_model: Optional[Type[T]] = None,
        max_retries: int = 3,
    ) -> Union[str, T]:
        """
        Invoke LLM with automatic retry on failure.

        Args:
            messages: List of LangChain message objects
            response_model: Optional Pydantic model for structured output
            max_retries: Maximum number of retry attempts

        Returns:
            Text response or structured model instance
        """
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                if response_model:
                    return await self.invoke_structured(messages, response_model)
                else:
                    return await self.invoke_text(messages)

            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    # Add exponential backoff if needed
                    import asyncio

                    await asyncio.sleep(2**attempt)
                    continue

        # If all retries failed, raise the last error
        self._log.error("llm.invoke.failed", error=str(last_error))
        raise last_error

    def create_messages(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[List[BaseMessage]] = None,
    ) -> List[BaseMessage]:
        """
        Utility method to create message list for common patterns.

        Args:
            user_prompt: User's input message
            system_prompt: Optional system message
            conversation_history: Optional previous messages

        Returns:
            List of BaseMessage objects ready for LLM invocation
        """
        messages = []

        # Add conversation history first
        if conversation_history:
            messages.extend(conversation_history)

        # Add system message if provided
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))

        # Add user message
        messages.append(HumanMessage(content=user_prompt))

        return messages

    async def invoke_simple(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        response_model: Optional[Type[T]] = None,
    ) -> Union[str, T]:
        """
        Simplified invoke method for single-turn interactions.

        Args:
            user_prompt: User's input message
            system_prompt: Optional system message
            response_model: Optional Pydantic model for structured output

        Returns:
            Text response or structured model instance
        """
        messages = self.create_messages(user_prompt, system_prompt)

        if response_model:
            return await self.invoke_structured(messages, response_model)
        else:
            return await self.invoke_text(messages)

    async def stream_text(self, messages: List[BaseMessage]):
        """
        Stream text response from LLM (for real-time generation).

        Args:
            messages: List of LangChain message objects

        Yields:
            Chunks of text as they arrive from LLM
        """
        async for chunk in self.llm.astream(messages):
            if hasattr(chunk, "content") and chunk.content:
                yield chunk.content
        self._log.info("llm.stream.end")

    def get_model_info(self) -> dict:
        """Get information about the current LLM configuration."""
        return {
            "model_name": self.llm.model_name,
            "temperature": self.llm.temperature,
            "max_tokens": self.llm.max_tokens,
        }
