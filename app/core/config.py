# app/core/config.py

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM Provider Settings
    OPENAI_API_KEY: str = ""

    # --- Operational Settings ---
    # DRAFT Tier
    DRAFT_MODEL: str = "gpt-4o-mini"
    DRAFT_MAX_CONCURRENCY: int = 12

    # DEFAULT Tier
    DEFAULT_MODEL: str = "gpt-4o-mini"
    DEFAULT_MAX_CONCURRENCY: int = 10

    # PREMIUM Tier
    PREMIUM_MODEL: str = "gpt-4o"
    PREMIUM_MAX_CONCURRENCY: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Create a single, reusable instance of the settings
settings = Settings()
