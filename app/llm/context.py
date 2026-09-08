"""Context manager for reconstructing conversation prompt payloads within token budgets."""

from app.core.config import settings
from app.llm.base import LLMMessage
from app.models.message import Message


class ContextManager:
    """Constructs ordered LLM prompt context from conversation history and system instructions."""

    def __init__(
        self,
        default_system_prompt: str | None = None,
        max_history_messages: int = 50,
    ) -> None:
        self.default_system_prompt = default_system_prompt or settings.default_system_prompt
        self.max_history_messages = max_history_messages

    def build_context(
        self,
        system_prompt: str | None,
        history: list[Message],
        current_prompt: str,
    ) -> list[LLMMessage]:
        """Assemble the complete chronological LLM prompt context.

        Structure:
        1. System prompt (custom conversation prompt or global default)
        2. Historical messages (chronologically ordered, bounded by max_history_messages)
        3. Current user prompt turn
        """
        effective_system_prompt = (
            system_prompt.strip()
            if system_prompt and system_prompt.strip()
            else self.default_system_prompt
        )

        context: list[LLMMessage] = [LLMMessage(role="system", content=effective_system_prompt)]

        # Apply sliding window truncation on history if exceeding max_history_messages
        trimmed_history = (
            history[-self.max_history_messages :]
            if len(history) > self.max_history_messages
            else history
        )

        for msg in trimmed_history:
            context.append(LLMMessage(role=msg.role, content=msg.content))

        # Add the active user turn
        context.append(LLMMessage(role="user", content=current_prompt))

        return context
