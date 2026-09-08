"""OpenAI LLM provider adapter using the official AsyncOpenAI SDK."""

import time
from collections.abc import AsyncIterator
from typing import Any, cast

from openai import AsyncOpenAI, AsyncStream
from openai.types.chat import ChatCompletionChunk

from app.core.config import settings
from app.llm.base import LLMMessage, LLMProvider, LLMResponse, LLMStreamChunk


class OpenAIProvider(LLMProvider):
    """Adapter for executing OpenAI chat completion requests."""

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.api_key = api_key or settings.openai_api_key
        self.default_model = default_model or settings.openai_model
        self.timeout_seconds = timeout_seconds or settings.openai_timeout_seconds

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            timeout=float(self.timeout_seconds),
        )

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Execute a non-streaming chat completion with OpenAI."""
        target_model = model or self.default_model
        target_temperature = temperature if temperature is not None else settings.openai_temperature
        target_max_tokens = max_tokens or settings.openai_max_output_tokens

        formatted_messages: list[dict[str, Any]] = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]

        start_time = time.perf_counter()

        response = await self.client.chat.completions.create(
            model=target_model,
            messages=cast(Any, formatted_messages),
            temperature=target_temperature,
            max_tokens=target_max_tokens,
        )

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        choice = response.choices[0]
        content = choice.message.content or ""
        usage = response.usage

        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else 0

        return LLMResponse(
            content=content,
            model=response.model or target_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=elapsed_ms,
        )

    async def generate_stream(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Execute a streaming chat completion with OpenAI, yielding token chunks."""
        target_model = model or self.default_model
        target_temperature = temperature if temperature is not None else settings.openai_temperature
        target_max_tokens = max_tokens or settings.openai_max_output_tokens

        formatted_messages: list[dict[str, Any]] = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]

        create_func = cast(Any, self.client.chat.completions.create)
        response = await create_func(
            model=target_model,
            messages=formatted_messages,
            temperature=target_temperature,
            max_tokens=target_max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )

        if not isinstance(response, AsyncStream):
            return

        stream: AsyncStream[ChatCompletionChunk] = response

        idx = 0
        async for chunk in stream:
            choice = chunk.choices[0] if chunk.choices else None
            delta_content = choice.delta.content if (choice and choice.delta) else ""
            finish_reason = choice.finish_reason if choice else None
            usage = chunk.usage
            prompt_tokens = usage.prompt_tokens if usage else None
            completion_tokens = usage.completion_tokens if usage else None
            total_tokens = usage.total_tokens if usage else None

            if delta_content:
                yield LLMStreamChunk(
                    delta=delta_content,
                    index=idx,
                    finish_reason=finish_reason,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                )
                idx += 1
            elif finish_reason is not None or usage is not None:
                yield LLMStreamChunk(
                    delta="",
                    index=idx,
                    finish_reason=finish_reason,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                )
