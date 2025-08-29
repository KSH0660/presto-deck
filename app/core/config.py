# app/core/config.py

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
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
    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    LOG_ROTATE_WHEN: str = "midnight"  # 'S', 'M', 'H', 'D', 'W0'-'W6', 'midnight'
    LOG_ROTATE_INTERVAL: int = 1  # Rotation interval for TimedRotatingFileHandler
    LOG_BACKUP_COUNT: int = 7  # Number of rotated files to keep
    LOG_FILE_BASENAME: str = "presto"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# Create a single, reusable instance of the settings
settings = Settings()
