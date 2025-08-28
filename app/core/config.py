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

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8"
    }


# Create a single, reusable instance of the settings
settings = Settings()
