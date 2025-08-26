import os
from dotenv import load_dotenv
import litellm
from litellm import Cache
from litellm.llms import ChatLiteLLM  # LiteLLM의 LangChain 통합

load_dotenv()

# LiteLLM 캐싱 설정 (인메모리 방식)
# 프로덕션 환경에서는 Redis와 같은 영구 저장소를 고려하세요.
litellm.cache = Cache(ttl=60 * 60)  # 1시간 캐시


def make_llm(model: str = "gpt-4o-mini", temperature: float = 0.2):
    """
    LLM 인스턴스를 생성하고 LiteLLM 캐싱을 적용합니다.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 필요합니다.")

    # LiteLLM의 LangChain 통합을 사용하여 캐싱 적용
    llm_instance = ChatLiteLLM(
        model=model,
        temperature=temperature,
        api_key=api_key,
        caching=True,  # 이 LiteLLM 인스턴스에 캐싱 활성화
    )
    return llm_instance
