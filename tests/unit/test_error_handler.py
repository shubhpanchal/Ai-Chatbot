"""Unit tests for centralized error formatting and exception handling."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import (
    AppException,
    ConversationNotFoundError,
    RateLimitExceededError,
    UnauthorizedError,
)
from app.main import app
from app.models.api_key import APIKey


@pytest.mark.asyncio
async def test_domain_exception_error_format() -> None:
    """Verify AppException subclasses are formatted into the standard error JSON envelope."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Define a temporary route on the app to raise specific domain errors
        @app.get("/test-error-401", include_in_schema=False)
        async def route_401() -> None:
            raise UnauthorizedError("Custom auth failure message.")

        @app.get("/test-error-404", include_in_schema=False)
        async def route_404() -> None:
            raise ConversationNotFoundError("Custom not found message.")

        @app.get("/test-error-429", include_in_schema=False)
        async def route_429() -> None:
            raise RateLimitExceededError("Too fast.")

        @app.get("/test-error-custom", include_in_schema=False)
        async def route_custom() -> None:
            raise AppException("Custom error", code="CUSTOM_CODE", status_code=418)

        # 401
        res_401 = await client.get("/test-error-401")
        assert res_401.status_code == 401
        data_401 = res_401.json()
        assert data_401["error"]["code"] == "UNAUTHORIZED"
        assert data_401["error"]["message"] == "Custom auth failure message."

        # 404
        res_404 = await client.get("/test-error-404")
        assert res_404.status_code == 404
        data_404 = res_404.json()
        assert data_404["error"]["code"] == "CONVERSATION_NOT_FOUND"
        assert data_404["error"]["message"] == "Custom not found message."

        # 429
        res_429 = await client.get("/test-error-429")
        assert res_429.status_code == 429
        data_429 = res_429.json()
        assert data_429["error"]["code"] == "RATE_LIMIT_EXCEEDED"

        # Custom
        res_custom = await client.get("/test-error-custom")
        assert res_custom.status_code == 418
        data_custom = res_custom.json()
        assert data_custom["error"]["code"] == "CUSTOM_CODE"


@pytest.mark.asyncio
async def test_validation_error_format(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify FastAPI schema validation errors return 422 with standard error envelope."""
    _, _, headers = primary_api_key
    # Attempting to query conversations with invalid page parameter (e.g. page=0)
    res = await async_client.get("/api/v1/conversations?page=0", headers=headers)
    assert res.status_code == 422
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert data["error"]["message"] == "Request validation failed."
    assert isinstance(data["error"]["details"], list)
