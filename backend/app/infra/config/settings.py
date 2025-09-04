"""
Application configuration settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", "../.env"], case_sensitive=False, extra="ignore"
    )

    # Application
    app_name: str = Field("Presto Deck API", alias="APP_NAME")

    # Environment
    environment: str = Field("development", alias="ENVIRONMENT")
    debug: bool = Field(False, alias="DEBUG")
    disable_auth: bool = Field(False, alias="DISABLE_AUTH")

    # Server
    host: str = Field("0.0.0.0", alias="HOST")
    port: int = Field(8000, alias="PORT")

    # Database
    database_url: str = Field(
        "sqlite+aiosqlite:///./presto_deck.db", alias="DATABASE_URL"
    )
    # PostgreSQL (for production/scaling)
    postgresql_url: str = Field(
        "postgresql+asyncpg://user:password@localhost:5432/presto_deck",
        alias="POSTGRESQL_URL",
    )
    debug_sql: bool = Field(False, alias="DATABASE_ECHO")

    # Redis
    redis_url: str = Field("redis://localhost:6379", alias="REDIS_URL")

    # ARQ Worker
    arq_redis_host: str = Field("localhost", alias="ARQ_REDIS_HOST")
    arq_redis_port: int = Field(6379, alias="ARQ_REDIS_PORT")
    arq_redis_database: int = Field(0, alias="ARQ_REDIS_DATABASE")
    arq_max_jobs: int = Field(10, alias="ARQ_MAX_JOBS")
    arq_job_timeout: int = Field(300, alias="ARQ_JOB_TIMEOUT")
    arq_max_tries: int = Field(3, alias="ARQ_MAX_TRIES")

    # JWT Authentication
    jwt_secret_key: str = Field(
        "dev-secret-key-change-in-production", alias="JWT_SECRET_KEY"
    )
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    jwt_expires_minutes: int = Field(30, alias="JWT_EXPIRATION_MINUTES")

    # OpenAI/LLM
    openai_api_key: str = Field("dummy-key-for-test", alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o-mini", alias="OPENAI_MODEL")
    llm_temperature: float = Field(0.3, alias="OPENAI_TEMPERATURE")
    llm_max_tokens: int = Field(4000, alias="OPENAI_MAX_TOKENS")

    # Assets and Templates
    assets_path: str = Field("assets", alias="ASSETS_PATH")

    # CORS
    cors_origins: str = Field("*", alias="CORS_ORIGINS")
    cors_allow_credentials: bool = Field(True, alias="CORS_ALLOW_CREDENTIALS")

    # Observability
    otel_service_name: str = Field("presto-deck", alias="OTEL_SERVICE_NAME")
    otel_exporter_otlp_endpoint: str = Field(
        "http://localhost:4317", alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    prometheus_metrics_enabled: bool = Field(True, alias="PROMETHEUS_METRICS_ENABLED")
    prometheus_metrics_port: int = Field(9090, alias="PROMETHEUS_METRICS_PORT")

    # Logging
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_format: str = Field("json", alias="LOG_FORMAT")

    # WebSocket
    websocket_heartbeat_interval: int = Field(30, alias="WS_HEARTBEAT_INTERVAL")

    def get_cors_origins(self) -> list[str]:
        """Parse CORS origins from string."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]


_settings = None


def get_settings() -> Settings:
    """Get settings instance (useful for dependency injection)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
