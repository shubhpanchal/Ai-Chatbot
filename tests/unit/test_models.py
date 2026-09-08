"""Unit tests for SQLAlchemy models and default values."""

import uuid
from decimal import Decimal

from app.models.api_key import APIKey
from app.models.conversation import Conversation
from app.models.llm_request import LLMRequest
from app.models.message import Message


def test_api_key_model_defaults() -> None:
    """Test APIKey model initialization and representation."""
    key = APIKey(
        name="test-key",
        key_hash="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    )
    assert key.name == "test-key"
    assert "test-key" in repr(key)


def test_conversation_model_defaults() -> None:
    """Test Conversation model initialization and properties."""
    api_key_id = uuid.uuid4()
    conv = Conversation(
        api_key_id=api_key_id,
        title="Test Conversation",
        system_prompt="Custom instruction",
    )
    assert conv.title == "Test Conversation"
    assert conv.api_key_id == api_key_id
    assert conv.is_deleted is False


def test_message_model_defaults() -> None:
    """Test Message model initialization and role validation."""
    conv_id = uuid.uuid4()
    msg = Message(
        conversation_id=conv_id,
        role="user",
        content="Hello world",
    )
    assert msg.conversation_id == conv_id
    assert msg.role == "user"
    assert msg.content == "Hello world"
    assert "user" in repr(msg)


def test_llm_request_model_defaults() -> None:
    """Test LLMRequest model initialization and decimal cost."""
    conv_id = uuid.uuid4()
    req = LLMRequest(
        conversation_id=conv_id,
        model="gpt-4o-mini",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        estimated_cost=Decimal("0.000045"),
        latency_ms=450,
        status="success",
    )
    assert req.model == "gpt-4o-mini"
    assert req.total_tokens == 150
    assert req.estimated_cost == Decimal("0.000045")
    assert req.status == "success"
    assert "gpt-4o-mini" in repr(req)
