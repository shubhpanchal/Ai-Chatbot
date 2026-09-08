"""Unit tests for context window construction and system prompt assembly."""

import uuid
from datetime import UTC, datetime

from app.llm.context import ContextManager
from app.models.message import Message


def test_context_manager_default_system_prompt() -> None:
    """Verify ContextManager uses default system prompt when custom prompt is absent."""
    manager = ContextManager(default_system_prompt="Default AI Assistant.")

    history: list[Message] = []
    context = manager.build_context(
        system_prompt=None,
        history=history,
        current_prompt="Hello!",
    )

    assert len(context) == 2
    assert context[0].role == "system"
    assert context[0].content == "Default AI Assistant."
    assert context[1].role == "user"
    assert context[1].content == "Hello!"


def test_context_manager_custom_system_prompt() -> None:
    """Verify ContextManager respects custom conversation-level system prompt."""
    manager = ContextManager()

    custom_prompt = "You are an expert Python asyncio instructor."
    context = manager.build_context(
        system_prompt=custom_prompt,
        history=[],
        current_prompt="What is asyncio?",
    )

    assert len(context) == 2
    assert context[0].role == "system"
    assert context[0].content == custom_prompt
    assert context[1].role == "user"
    assert context[1].content == "What is asyncio?"


def test_context_manager_chronological_history_assembly() -> None:
    """Verify ContextManager correctly structures multi-turn history."""
    manager = ContextManager()

    conv_id = uuid.uuid4()
    msg1 = Message(
        id=uuid.uuid4(),
        conversation_id=conv_id,
        role="user",
        content="Question 1",
        created_at=datetime.now(UTC),
    )
    msg2 = Message(
        id=uuid.uuid4(),
        conversation_id=conv_id,
        role="assistant",
        content="Answer 1",
        created_at=datetime.now(UTC),
    )

    context = manager.build_context(
        system_prompt="Custom prompt",
        history=[msg1, msg2],
        current_prompt="Question 2",
    )

    assert len(context) == 4
    assert context[0].role == "system"
    assert context[1].role == "user"
    assert context[1].content == "Question 1"
    assert context[2].role == "assistant"
    assert context[2].content == "Answer 1"
    assert context[3].role == "user"
    assert context[3].content == "Question 2"


def test_context_manager_sliding_window_truncation() -> None:
    """Verify ContextManager preserves system prompt and active turn while trimming old history."""
    max_history = 4
    manager = ContextManager(max_history_messages=max_history)

    conv_id = uuid.uuid4()
    history = [
        Message(
            id=uuid.uuid4(),
            conversation_id=conv_id,
            role="user" if i % 2 == 0 else "assistant",
            content=f"Message {i}",
            created_at=datetime.now(UTC),
        )
        for i in range(10)
    ]

    context = manager.build_context(
        system_prompt="System instructions",
        history=history,
        current_prompt="Active User Turn",
    )

    # 1 system + 4 trimmed history + 1 active user = 6 total
    assert len(context) == 6
    assert context[0].role == "system"
    assert context[1].content == "Message 6"
    assert context[4].content == "Message 9"
    assert context[5].role == "user"
    assert context[5].content == "Active User Turn"
