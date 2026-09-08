"""Domain and application exception hierarchy."""

from typing import Any


class AppException(Exception):
    """Base exception for all domain and application errors."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = 500,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class UnauthorizedError(AppException):
    """Raised when authentication fails (missing, invalid, or inactive API key)."""

    def __init__(
        self,
        message: str = "Missing, invalid, or inactive API key.",
        details: Any = None,
    ) -> None:
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=401,
            details=details,
        )


class ForbiddenError(AppException):
    """Raised when an authenticated client lacks permissions for an operation."""

    def __init__(
        self,
        message: str = "Access to the requested resource is forbidden.",
        details: Any = None,
    ) -> None:
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=403,
            details=details,
        )


class ConversationNotFoundError(AppException):
    """Raised when a requested conversation is not found, deleted, or owned by another tenant."""

    def __init__(
        self,
        message: str = "Conversation not found.",
        details: Any = None,
    ) -> None:
        super().__init__(
            message=message,
            code="CONVERSATION_NOT_FOUND",
            status_code=404,
            details=details,
        )


class EntityNotFoundError(AppException):
    """Generic not found error for database entities."""

    def __init__(
        self,
        message: str = "Requested resource not found.",
        code: str = "NOT_FOUND",
        details: Any = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=404,
            details=details,
        )


class ValidationError(AppException):
    """Raised when business validation rules are violated."""

    def __init__(
        self,
        message: str = "Request payload validation failed.",
        details: Any = None,
    ) -> None:
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details=details,
        )


class RateLimitExceededError(AppException):
    """Raised when an API key exceeds its rate limit."""

    def __init__(
        self,
        message: str = "Rate limit exceeded. Please retry later.",
        details: Any = None,
    ) -> None:
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details=details,
        )


class IdempotencyConflictError(AppException):
    """Raised when an in-flight request with the same Idempotency-Key is detected."""

    def __init__(
        self,
        message: str = "A request with this Idempotency-Key is currently in progress.",
        details: Any = None,
    ) -> None:
        super().__init__(
            message=message,
            code="IDEMPOTENCY_CONFLICT",
            status_code=409,
            details=details,
        )


class LLMTimeoutError(AppException):
    """Raised when an upstream LLM call exceeds the configured timeout."""

    def __init__(
        self,
        message: str = "Upstream LLM request timed out.",
        details: Any = None,
    ) -> None:
        super().__init__(
            message=message,
            code="LLM_TIMEOUT",
            status_code=504,
            details=details,
        )


class LLMProviderError(AppException):
    """Raised when an unrecoverable error is returned from the LLM provider."""

    def __init__(
        self,
        message: str = "Upstream LLM provider returned an unrecoverable error.",
        details: Any = None,
    ) -> None:
        super().__init__(
            message=message,
            code="LLM_PROVIDER_ERROR",
            status_code=502,
            details=details,
        )


class ServiceUnavailableError(AppException):
    """Raised when a core infrastructure service (Postgres/Redis) is unavailable."""

    def __init__(
        self,
        message: str = "Service temporarily unavailable.",
        details: Any = None,
    ) -> None:
        super().__init__(
            message=message,
            code="SERVICE_UNAVAILABLE",
            status_code=503,
            details=details,
        )
