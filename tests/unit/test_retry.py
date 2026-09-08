"""Unit tests for exponential backoff, jitter, and selective retry logic."""

import httpx
import openai
import pytest

from app.core.retry import compute_backoff_delay, is_transient_error, with_retry


def test_is_transient_error_classification() -> None:
    """Verify transient error classification matches retry rules."""
    req = httpx.Request("POST", "http://test")
    res_429 = httpx.Response(429, request=req)
    res_500 = httpx.Response(500, request=req)
    res_400 = httpx.Response(400, request=req)
    res_401 = httpx.Response(401, request=req)

    # Transient errors -> True
    assert is_transient_error(httpx.HTTPStatusError(message="429", request=req, response=res_429))
    assert is_transient_error(httpx.HTTPStatusError(message="500", request=req, response=res_500))
    assert is_transient_error(httpx.ConnectTimeout("Connect timeout", request=req))
    assert is_transient_error(httpx.ReadTimeout("Read timeout", request=req))
    assert is_transient_error(TimeoutError("Generic timeout"))
    assert is_transient_error(openai.APIConnectionError(request=req))  # type: ignore[arg-type]
    assert is_transient_error(openai.APITimeoutError(request=req))  # type: ignore[arg-type]

    # Non-transient errors -> False
    assert not is_transient_error(
        httpx.HTTPStatusError(message="400", request=req, response=res_400)
    )
    assert not is_transient_error(
        httpx.HTTPStatusError(message="401", request=req, response=res_401)
    )
    assert not is_transient_error(ValueError("Invalid argument"))


def test_compute_backoff_delay_boundaries() -> None:
    """Verify exponential backoff calculation and jitter bounds."""
    # Without jitter
    d1 = compute_backoff_delay(attempt=1, base_delay=0.5, max_delay=8.0, jitter=False)
    assert d1 == 0.5

    d2 = compute_backoff_delay(attempt=2, base_delay=0.5, max_delay=8.0, jitter=False)
    assert d2 == 1.0

    d3 = compute_backoff_delay(attempt=3, base_delay=0.5, max_delay=8.0, jitter=False)
    assert d3 == 2.0

    d10 = compute_backoff_delay(attempt=10, base_delay=0.5, max_delay=8.0, jitter=False)
    assert d10 == 8.0  # capped at max_delay

    # With jitter: delay in [0, exponential_delay]
    for attempt in range(1, 5):
        j_delay = compute_backoff_delay(attempt=attempt, base_delay=0.5, max_delay=8.0, jitter=True)
        max_possible = min(8.0, 0.5 * (2 ** (attempt - 1)))
        assert 0.0 <= j_delay <= max_possible


@pytest.mark.asyncio
async def test_with_retry_success_after_transient_failures() -> None:
    """Verify with_retry recovers after transient failures before max_attempts."""
    attempts = 0

    async def flaky_operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise TimeoutError("Simulated transient network timeout")
        return "success"

    result = await with_retry(
        flaky_operation,
        max_attempts=3,
        base_delay=0.01,
        max_delay=0.05,
    )
    assert result == "success"
    assert attempts == 3


@pytest.mark.asyncio
async def test_with_retry_aborts_immediately_on_non_transient_error() -> None:
    """Verify with_retry does NOT retry permanent errors."""
    attempts = 0

    async def fatal_operation() -> None:
        nonlocal attempts
        attempts += 1
        raise ValueError("Non-transient bad argument")

    with pytest.raises(ValueError, match="Non-transient bad argument"):
        await with_retry(
            fatal_operation,
            max_attempts=3,
            base_delay=0.01,
        )

    assert attempts == 1  # Aborted on first try


@pytest.mark.asyncio
async def test_with_retry_exceeds_max_attempts() -> None:
    """Verify with_retry raises the exception when max_attempts is exhausted."""
    attempts = 0

    async def always_failing() -> None:
        nonlocal attempts
        attempts += 1
        raise TimeoutError("Persistent timeout")

    with pytest.raises(TimeoutError, match="Persistent timeout"):
        await with_retry(
            always_failing,
            max_attempts=3,
            base_delay=0.01,
        )

    assert attempts == 3
