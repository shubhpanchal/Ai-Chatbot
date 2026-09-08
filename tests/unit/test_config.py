"""Unit tests for application configuration and settings."""

from app.core.config import Settings


def test_default_settings() -> None:
    """Test that default settings initialize with expected values."""
    settings = Settings()

    assert settings.app_name == "AI Chat API"
    assert settings.app_env in ["development", "testing", "staging", "production"]
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.rate_limit_requests == 100
    assert settings.rate_limit_window_seconds == 60
    assert settings.openai_timeout_seconds == 30
    assert settings.db_connect_timeout_seconds == 5
    assert settings.db_command_timeout_seconds == 10
    assert settings.redis_socket_timeout_seconds == 2


def test_environment_helpers() -> None:
    """Test environment boolean helper properties."""
    dev_settings = Settings(APP_ENV="development")
    assert dev_settings.is_development is True
    assert dev_settings.is_testing is False
    assert dev_settings.is_production is False

    test_settings = Settings(APP_ENV="testing")
    assert test_settings.is_development is False
    assert test_settings.is_testing is True
    assert test_settings.is_production is False

    prod_settings = Settings(APP_ENV="production")
    assert prod_settings.is_development is False
    assert prod_settings.is_testing is False
    assert prod_settings.is_production is True
