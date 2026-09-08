"""Structured logging configuration using structlog."""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any, cast

import structlog

from app.core.config import settings

# Sensitive key patterns to redact automatically from logs
SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "password",
    "secret",
    "token",
    "raw_key",
    "key_hash",
    "api_key_secret",
    "content",
    "prompt",
}

API_KEY_PATTERN = re.compile(r"ak_[a-zA-Z0-9_-]{20,}")
BEARER_PATTERN = re.compile(r"Bearer\s+[a-zA-Z0-9_\.-]+", re.IGNORECASE)


def redact_sensitive_data(
    logger: Any,
    method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Redact sensitive credentials, secrets, and raw user prompt content from log events."""
    for key, value in list(event_dict.items()):
        key_lower = key.lower()

        # 1. Redact if the key matches known sensitive names
        if any(sensitive_term in key_lower for sensitive_term in SENSITIVE_KEYS):
            if isinstance(value, str):
                event_dict[key] = "[REDACTED]"
            elif isinstance(value, (dict, list)):
                event_dict[key] = "[REDACTED_PAYLOAD]"

        # 2. Check if string values contain embedded API keys or Bearer tokens
        elif isinstance(value, str):
            if API_KEY_PATTERN.search(value):
                value = API_KEY_PATTERN.sub("ak_[REDACTED]", value)
            if BEARER_PATTERN.search(value):
                value = BEARER_PATTERN.sub("Bearer [REDACTED]", value)
            event_dict[key] = value

    return event_dict


def configure_logging() -> None:
    """Configure structlog processors, standard library redirection, and formatters."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        redact_sensitive_data,
    ]

    if settings.is_production or settings.is_testing:
        # Structured JSON rendering for production / automated tests
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        # Human-readable colored console rendering for development
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Suppress verbose noisy logs from third party libraries
    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.access").propagate = False
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger instance."""
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
