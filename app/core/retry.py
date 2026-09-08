"""Resilience and retry utilities with exponential backoff and full jitter."""

import asyncio
import logging
import random
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

import httpx
import openai

logger = logging.getLogger(__name__)

T = TypeVar("T")


def is_transient_error(exc: Exception) -> bool:
    """Classify whether an exception is genuinely transient and safe to retry.

    Retries:
    - 429 RateLimitError
    - 500, 502, 503, 504 Server errors
    - Connection timeouts, network drops, and socket errors

    Rejects / Does NOT retry:
    - 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 Validation
    - Permanent client or configuration errors
    """
    # OpenAI SDK specific exceptions
    if isinstance(
        exc,
        (
            openai.RateLimitError,
            openai.InternalServerError,
            openai.APITimeoutError,
            openai.APIConnectionError,
        ),
    ):
        return True
    if isinstance(
        exc,
        (
            openai.AuthenticationError,
            openai.BadRequestError,
            openai.NotFoundError,
            openai.PermissionDeniedError,
            openai.UnprocessableEntityError,
        ),
    ):
        return False

    # HTTPX networking exceptions
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return bool(status == 429 or 500 <= status <= 599)

    # Standard asyncio timeouts
    return isinstance(exc, (TimeoutError, asyncio.TimeoutError))


def compute_backoff_delay(
    attempt: int,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    jitter: bool = True,
) -> float:
    """Compute exponential backoff delay with full jitter.

    Formula: min(max_delay, base_delay * 2^(attempt - 1))
    Full jitter selects uniformly in [0, computed_delay].
    """
    exponential_delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
    if jitter:
        return float(random.uniform(0, exponential_delay))
    return float(exponential_delay)


async def with_retry(
    func: Callable[[], Coroutine[Any, Any, T]],
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    is_transient_fn: Callable[[Exception], bool] = is_transient_error,
) -> T:
    """Execute an async callable with automatic retries on transient errors."""
    for attempt in range(1, max_attempts + 1):
        try:
            return await func()
        except Exception as exc:
            is_transient = is_transient_fn(exc)
            if not is_transient or attempt >= max_attempts:
                logger.warning(
                    "Operation failed permanently on attempt %d/%d (transient=%s): %s",
                    attempt,
                    max_attempts,
                    is_transient,
                    str(exc),
                )
                raise

            delay = compute_backoff_delay(
                attempt=attempt,
                base_delay=base_delay,
                max_delay=max_delay,
                jitter=True,
            )
            logger.info(
                "Transient failure on attempt %d/%d (%s). Retrying in %.3fs...",
                attempt,
                max_attempts,
                type(exc).__name__,
                delay,
            )
            await asyncio.sleep(delay)

    raise RuntimeError("Unreachable retry state.")
