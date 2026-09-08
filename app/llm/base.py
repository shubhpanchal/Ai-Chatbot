"""Abstract base classes and data contracts for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMMessage:
    """Represents a single message in the LLM conversation payload."""

    role: str
    content: str


@dataclass(frozen=True)
class LLMResponse:
    """Represents the complete result returned from an LLM generation call."""

    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int


class LLMProvider(ABC):
    """Abstract interface for large language model providers."""

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Execute a synchronous generation call given a prompt context."""
        raise NotImplementedError
