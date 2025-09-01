from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    app_name: str = "Presto-Deck API"
    version: str = "0.1.0"
    debug: bool = False
    environment: str = Field(default="development")

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/presto_deck",
    )
    database_echo: bool = Field(default=False)

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
    )
    redis_stream_key: str = Field(default="deck_events")
    redis_pubsub_key: str = Field(default="deck_notifications")

    # JWT Authentication
    jwt_secret_key: str = Field(
        default="your-super-secret-jwt-key-change-in-production",
    )
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiration_minutes: int = Field(default=1440)  # 24 hours

    # OpenAI/LLM
    openai_api_key: Optional[str] = Field(default=None)
    openai_model: str = Field(default="gpt-4")
    openai_max_tokens: int = Field(default=4000)
    openai_temperature: float = Field(default=0.7)

    # ARQ Worker
    arq_max_jobs: int = Field(default=10)
    arq_job_timeout: int = Field(default=300)  # 5 minutes
    arq_max_tries: int = Field(default=3)

    # CORS
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8080",
    )
    cors_allow_credentials: bool = Field(default=True)

    # Security
    html_sanitizer_tags: list[str] = Field(
        default=[
            "p",
            "br",
            "strong",
            "em",
            "u",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "ul",
            "ol",
            "li",
            "blockquote",
            "code",
            "pre",
            "div",
            "span",
            "img",
            "a",
            "table",
            "thead",
            "tbody",
            "tr",
            "th",
            "td",
        ],
    )
    html_sanitizer_attributes: dict[str, list[str]] = Field(
        default={
            "img": ["src", "alt", "width", "height"],
            "a": ["href", "title"],
            "div": ["class"],
            "span": ["class"],
            "table": ["class"],
            "th": ["class"],
            "td": ["class"],
        },
    )

    # Observability
    otel_service_name: str = Field(default="presto-deck")
    otel_exporter_otlp_endpoint: Optional[str] = Field(default=None)
    otel_resource_attributes: str = Field(
        default="service.name=presto-deck,service.version=0.1.0",
    )
    prometheus_metrics_enabled: bool = Field(default=True)
    prometheus_metrics_port: int = Field(default=9090)

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")  # json or text

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    def get_redis_arq_url(self) -> str:
        """Get Redis URL formatted for ARQ."""
        return self.redis_url.replace("redis://", "redis://").rstrip("/0") + "/1"

    def get_cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"

    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.environment.lower() == "testing"


# Global settings instance
settings = Settings()
