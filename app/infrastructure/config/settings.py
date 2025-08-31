"""애플리케이션 설정"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """애플리케이션 설정"""

    # API 설정
    API_TITLE: str = "Presto API"
    API_VERSION: str = "2.0.0"
    API_DESCRIPTION: str = (
        "AI-powered presentation slide generator with clean architecture"
    )

    # LLM 설정
    OPENAI_API_KEY: Optional[str] = None
    DEFAULT_MODEL: str = "gpt-4o-mini"
    PREMIUM_MODEL: str = "gpt-4o"

    # 동시성 설정
    DEFAULT_CONCURRENCY: int = 3
    PREMIUM_CONCURRENCY: int = 5

    # 저장소 설정
    USE_REDIS: bool = False
    REDIS_URL: Optional[str] = "redis://localhost:6379"

    # 모니터링
    ENABLE_METRICS: bool = True
    LOG_LEVEL: str = "INFO"

    # 템플릿 설정
    TEMPLATE_DIR: str = "templates"

    class Config:
        env_file = ".env"
        case_sensitive = True


# 전역 설정 인스턴스
settings = Settings()
