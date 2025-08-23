import os
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from dotenv import load_dotenv
from pydantic import BaseModel

from typing import TypeVar, Union, cast

T = TypeVar("T", bound=BaseModel)

load_dotenv()

aclient = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def generate_content_openai(
    prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    model: str = "gpt-4o",
    response_model: type[BaseModel] | None = None,
) -> Union[str, T]:
    messages: list[ChatCompletionMessageParam] = [
        {"role": "user", "content": prompt},
    ]

    if response_model:
        resp = await aclient.responses.parse(
            model=model,
            input=messages,
            temperature=temperature,
            text_format=response_model,
        )
        return cast(T, resp.output_parsed)
    else:
        response = await aclient.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
