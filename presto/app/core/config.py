from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    PROMPT_DIR: str = os.path.join("presto", "prompts")
    TEMPLATE_DIR: str = os.path.join("presto", "templates")

settings = Settings()
