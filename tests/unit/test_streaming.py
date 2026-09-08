"""Unit tests for LLM streaming abstractions and mock streaming provider."""

import pytest

from app.llm.base import LLMMessage, LLMStreamChunk
from app.llm.mock import MockLLMProvider
from app.schemas.message import StreamDoneEvent, StreamTokenEvent


@pytest.mark.asyncio
async def test_mock_llm_provider_streaming_chunks() -> None:
    """Verify MockLLMProvider yields incremental token chunks and final metadata."""
    provider = MockLLMProvider(
        default_response="Alpha beta gamma",
        simulated_latency_ms=0,
    )
    messages = [
        LLMMessage(role="system", content="System prompt"),
        LLMMessage(role="user", content="User prompt"),
    ]

    chunks: list[LLMStreamChunk] = []
    async for chunk in provider.generate_stream(messages=messages):
        chunks.append(chunk)

    assert len(chunks) > 0
    # Last chunk is the metadata / stop chunk
    last_chunk = chunks[-1]
    assert last_chunk.finish_reason == "stop"
    assert last_chunk.prompt_tokens is not None and last_chunk.prompt_tokens > 0
    assert last_chunk.completion_tokens is not None and last_chunk.completion_tokens > 0
    assert last_chunk.total_tokens == last_chunk.prompt_tokens + last_chunk.completion_tokens

    # Verify content chunks
    token_chunks = chunks[:-1]
    reconstructed = "".join(c.delta for c in token_chunks)
    assert "Alpha beta gamma" in reconstructed

    # Verify indices
    for i, c in enumerate(token_chunks):
        assert c.index == i


@pytest.mark.asyncio
async def test_mock_llm_provider_streaming_error_injection() -> None:
    """Verify MockLLMProvider raises simulated errors during stream initialization."""
    provider = MockLLMProvider(
        simulated_error=RuntimeError("Provider stream connection reset"),
    )
    messages = [LLMMessage(role="user", content="Hello")]

    with pytest.raises(RuntimeError, match="Provider stream connection reset"):
        async for _ in provider.generate_stream(messages=messages):
            pass


def test_sse_event_schemas() -> None:
    """Verify serialization of StreamTokenEvent and StreamDoneEvent."""
    token_event = StreamTokenEvent(token=" Hello", index=3)
    assert token_event.token == " Hello"
    assert token_event.index == 3
    assert token_event.model_dump() == {"token": " Hello", "index": 3}

    import uuid

    msg_id = uuid.uuid4()
    done_event = StreamDoneEvent(
        message_id=msg_id,
        total_tokens=150,
        estimated_cost_usd=0.000045,
        finish_reason="stop",
    )
    dumped = done_event.model_dump()
    assert dumped["message_id"] == msg_id
    assert dumped["total_tokens"] == 150
    assert dumped["estimated_cost_usd"] == 0.000045
    assert dumped["finish_reason"] == "stop"
