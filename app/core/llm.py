import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain.globals import set_llm_cache
from langchain_community.cache import SQLiteCache

load_dotenv()

# LangChain SQLite 캐싱 설정
set_llm_cache(SQLiteCache(database_path=".langchain.db"))


def make_llm(model: str = "gpt-4o-mini", temperature: float = 0.2) -> ChatOpenAI:
    """
    LLM 인스턴스를 생성합니다. LangChain SQLite 캐싱이 적용됩니다.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 필요합니다.")

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        temperature=temperature,
        timeout=60,
    )
