"""Application configuration management using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable parsing and validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -------------------------------------------------------------------------
    # Application Metadata
    # -------------------------------------------------------------------------
    app_name: str = Field(default="AI Chat API", alias="APP_NAME")
    app_env: Literal["development", "testing", "staging", "production"] = Field(
        default="development", alias="APP_ENV"
    )
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    debug: bool = Field(default=False, alias="DEBUG")
    http_server_timeout_seconds: int = Field(default=60, alias="HTTP_SERVER_TIMEOUT_SECONDS")

    # -------------------------------------------------------------------------
    # Database Configuration (PostgreSQL)
    # -------------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/ai_chat_db",
        alias="DATABASE_URL",
    )
    db_connect_timeout_seconds: int = Field(default=5, alias="DB_CONNECT_TIMEOUT_SECONDS")
    db_command_timeout_seconds: int = Field(default=10, alias="DB_COMMAND_TIMEOUT_SECONDS")
    db_pool_size: int = Field(default=10, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, alias="DB_MAX_OVERFLOW")
    db_pool_recycle_seconds: int = Field(default=1800, alias="DB_POOL_RECYCLE_SECONDS")

    # -------------------------------------------------------------------------
    # Redis Configuration
    # -------------------------------------------------------------------------
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_socket_timeout_seconds: int = Field(default=2, alias="REDIS_SOCKET_TIMEOUT_SECONDS")
    redis_connect_timeout_seconds: int = Field(default=5, alias="REDIS_CONNECT_TIMEOUT_SECONDS")

    # -------------------------------------------------------------------------
    # Security & Authentication
    # -------------------------------------------------------------------------
    api_key_secret: str = Field(
        default="dev-secret-pepper-key-minimum-32-chars-change-in-production",
        alias="API_KEY_SECRET",
    )
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["*"], alias="CORS_ALLOW_ORIGINS")

    # -------------------------------------------------------------------------
    # Rate Limiting & Idempotency
    # -------------------------------------------------------------------------
    rate_limit_requests: int = Field(default=100, alias="RATE_LIMIT_REQUESTS")
    rate_limit_window_seconds: int = Field(default=60, alias="RATE_LIMIT_WINDOW_SECONDS")
    rate_limit_fail_open: bool = Field(default=False, alias="RATE_LIMIT_FAIL_OPEN")
    idempotency_ttl_seconds: int = Field(default=86400, alias="IDEMPOTENCY_TTL_SECONDS")
    idempotency_lock_timeout_seconds: int = Field(
        default=60, alias="IDEMPOTENCY_LOCK_TIMEOUT_SECONDS"
    )

    # -------------------------------------------------------------------------
    # LLM Provider Configuration
    # -------------------------------------------------------------------------
    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    openai_api_key: str = Field(default="sk-test-key-placeholder", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_temperature: float = Field(default=0.7, alias="OPENAI_TEMPERATURE")
    openai_max_output_tokens: int = Field(default=2048, alias="OPENAI_MAX_OUTPUT_TOKENS")
    openai_timeout_seconds: int = Field(default=30, alias="OPENAI_TIMEOUT_SECONDS")
    openai_max_retries: int = Field(default=3, alias="OPENAI_MAX_RETRIES")
    default_system_prompt: str = Field(
        default="You are a helpful, accurate, and concise AI assistant.",
        alias="DEFAULT_SYSTEM_PROMPT",
    )

    @property
    def is_development(self) -> bool:
        """Check if current environment is development."""
        return self.app_env == "development"

    @property
    def is_testing(self) -> bool:
        """Check if current environment is testing."""
        return self.app_env == "testing"

    @property
    def is_production(self) -> bool:
        """Check if current environment is production."""
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()


# Global settings instance for convenient import
settings = get_settings()
