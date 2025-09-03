"""
Application configuration settings.
"""

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    # Database
    database_url: str = Field(..., env="DATABASE_URL")

    # Redis
    redis_url: str = Field("redis://localhost:6379", env="REDIS_URL")

    # ARQ Worker
    arq_redis_host: str = Field("localhost", env="ARQ_REDIS_HOST")
    arq_redis_port: int = Field(6379, env="ARQ_REDIS_PORT")
    arq_redis_database: int = Field(0, env="ARQ_REDIS_DATABASE")

    # JWT Authentication
    jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field("HS256", env="JWT_ALGORITHM")
    jwt_expires_minutes: int = Field(30, env="JWT_EXPIRES_MINUTES")

    # OpenAI/LLM
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    llm_model: str = Field("gpt-4o-mini", env="LLM_MODEL")
    llm_temperature: float = Field(0.3, env="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(4000, env="LLM_MAX_TOKENS")

    # Application
    app_name: str = Field("Presto Deck API", env="APP_NAME")
    debug: bool = Field(False, env="DEBUG")
    cors_origins: str = Field("*", env="CORS_ORIGINS")

    # WebSocket
    websocket_heartbeat_interval: int = Field(30, env="WS_HEARTBEAT_INTERVAL")

    class Config:
        env_file = ".env"
        case_sensitive = False

    def get_cors_origins(self) -> list[str]:
        """Parse CORS origins from string."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]


# Global settings instance
settings = Settings()
