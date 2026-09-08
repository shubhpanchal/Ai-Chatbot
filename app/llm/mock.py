"""Deterministic mock LLM provider for zero-cost testing and local validation."""

import asyncio
import time
from collections.abc import Callable

from app.llm.base import LLMMessage, LLMProvider, LLMResponse


class MockLLMProvider(LLMProvider):
    """Deterministic, configurable fake LLM provider."""

    def __init__(
        self,
        default_response: str = "This is a deterministic test response from MockLLMProvider.",
        response_generator: Callable[[list[LLMMessage]], str] | None = None,
        simulated_latency_ms: int = 20,
        simulated_error: Exception | None = None,
        transient_failures_before_success: int = 0,
        prompt_tokens_per_message: int = 10,
        completion_tokens_per_response: int = 15,
    ) -> None:
        self.default_response = default_response
        self.response_generator = response_generator
        self.simulated_latency_ms = simulated_latency_ms
        self.simulated_error = simulated_error
        self.transient_failures_before_success = transient_failures_before_success
        self.prompt_tokens_per_message = prompt_tokens_per_message
        self.completion_tokens_per_response = completion_tokens_per_response

        # Tracking state for assertions
        self.call_count: int = 0
        self.last_messages: list[LLMMessage] = []
        self._current_failure_count: int = 0

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Simulate LLM generation with failure injection and latency simulation."""
        self.call_count += 1
        self.last_messages = messages
        start_time = time.perf_counter()

        # Simulate transient failure injection
        if self._current_failure_count < self.transient_failures_before_success:
            self._current_failure_count += 1
            if self.simulated_error:
                raise self.simulated_error
            raise TimeoutError("Simulated transient upstream timeout.")

        # Simulate permanent error injection
        if self.simulated_error and self.transient_failures_before_success == 0:
            raise self.simulated_error

        # Simulate network latency
        if self.simulated_latency_ms > 0:
            await asyncio.sleep(self.simulated_latency_ms / 1000.0)

        # Generate content
        if self.response_generator:
            content = self.response_generator(messages)
        else:
            last_prompt = messages[-1].content if messages else ""
            content = f"{self.default_response} (Prompt was: '{last_prompt}')"

        prompt_tokens = len(messages) * self.prompt_tokens_per_message
        completion_tokens = max(1, len(content.split())) * 2
        total_tokens = prompt_tokens + completion_tokens
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        return LLMResponse(
            content=content,
            model=model or "mock-model",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=elapsed_ms,
        )
