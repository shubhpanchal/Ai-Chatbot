"""Unit tests for LLM providers (MockLLMProvider and OpenAIProvider adapter)."""

import pytest

from app.llm.base import LLMMessage
from app.llm.mock import MockLLMProvider
from app.llm.openai import OpenAIProvider


@pytest.mark.asyncio
async def test_mock_llm_provider_generation() -> None:
    """Verify MockLLMProvider generates deterministic replies and computes simulated tokens."""
    provider = MockLLMProvider(default_response="Mock reply")

    messages = [
        LLMMessage(role="system", content="System instruction"),
        LLMMessage(role="user", content="Hello test"),
    ]

    response = await provider.generate(messages=messages, model="test-mock")
    assert response.content.startswith("Mock reply")
    assert response.model == "test-mock"
    assert response.prompt_tokens == 20  # 2 messages * 10
    assert response.completion_tokens > 0
    assert response.total_tokens == response.prompt_tokens + response.completion_tokens
    assert provider.call_count == 1
    assert provider.last_messages == messages


@pytest.mark.asyncio
async def test_mock_llm_provider_transient_failure_simulation() -> None:
    """Verify MockLLMProvider can simulate transient failures before succeeding."""
    provider = MockLLMProvider(
        default_response="Recovered reply",
        transient_failures_before_success=2,
    )

    messages = [LLMMessage(role="user", content="Test retry")]

    # First call fails
    with pytest.raises(TimeoutError):
        await provider.generate(messages=messages)

    # Second call fails
    with pytest.raises(TimeoutError):
        await provider.generate(messages=messages)

    # Third call succeeds
    response = await provider.generate(messages=messages)
    assert response.content.startswith("Recovered reply")
    assert provider.call_count == 3


def test_openai_provider_initialization() -> None:
    """Verify OpenAIProvider initializes AsyncOpenAI client with config settings."""
    provider = OpenAIProvider(
        api_key="sk-test-sample-key",
        default_model="gpt-4o-mini",
        timeout_seconds=25,
    )
    assert provider.api_key == "sk-test-sample-key"
    assert provider.default_model == "gpt-4o-mini"
    assert provider.timeout_seconds == 25
    assert provider.client is not None
