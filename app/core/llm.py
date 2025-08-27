from langchain_openai import ChatOpenAI
from langchain.globals import set_llm_cache
from langchain_community.cache import SQLiteCache
from app.core.config import settings
import logging  # Added

logger = logging.getLogger(__name__)  # Added

# LangChain SQLite 캐싱 설정
set_llm_cache(SQLiteCache(database_path=".langchain.db"))


def make_llm(
    model: str = settings.DEFAULT_MODEL, temperature: float = 0.2
) -> ChatOpenAI:
    """
    LLM 인스턴스를 생성합니다. LangChain SQLite 캐싱이 적용됩니다.
    """
    logger.info(
        "Creating LLM instance with model: %s, temperature: %s", model, temperature
    )  # Added
    return ChatOpenAI(
        model=model,
        api_key=settings.OPENAI_API_KEY,
        temperature=temperature,
        timeout=60,
    )
