# app/core/infra/config.py

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """애플리케이션 설정을 관리합니다 (.env 로딩)."""

    # LLM Provider Settings
    OPENAI_API_KEY: str = ""

    # --- Operational Settings ---
    # DRAFT Tier
    DRAFT_MODEL: str = "gpt-5-nano"
    DRAFT_MAX_CONCURRENCY: int = 36

    # DEFAULT Tier
    DEFAULT_MODEL: str = "gpt-5-mini"
    DEFAULT_MAX_CONCURRENCY: int = 24

    # PREMIUM Tier
    PREMIUM_MODEL: str = "gpt-5"
    PREMIUM_MAX_CONCURRENCY: int = 12

    # Global limits and toggles
    MAX_CONCURRENCY_LIMIT: int = 48
    HEARTBEAT_INTERVAL_SEC: int = 15

    # Logging
    LOG_DIR: str = "logs"
    LOG_LEVEL: str = "INFO"
    LOG_ROTATE_WHEN: str = "midnight"
    LOG_ROTATE_INTERVAL: int = 1
    LOG_BACKUP_COUNT: int = 7
    LOG_FILE_BASENAME: str = "presto"

    # Metrics / Feature toggles
    ENABLE_METRICS: bool = True

    # Redis (optional)
    USE_REDIS: bool = False
    REDIS_URL: str = "redis://localhost:6379/0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# Singleton settings instance
settings = Settings()
