import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()


def make_llm(model: str = "gpt-4o-mini", temperature: float = 0.2) -> ChatOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 필요합니다.")

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        temperature=temperature,
    )
