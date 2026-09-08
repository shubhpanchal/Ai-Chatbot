"""FastAPI dependency providers for authentication, database sessions, and services."""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.security import hash_api_key
from app.db.redis import get_redis_client
from app.db.session import get_async_session
from app.llm.base import LLMProvider
from app.llm.mock import MockLLMProvider
from app.llm.openai import OpenAIProvider
from app.models.api_key import APIKey
from app.repositories.api_key import APIKeyRepository
from app.repositories.conversation import ConversationRepository
from app.repositories.llm_request import LLMRequestRepository
from app.repositories.message import MessageRepository
from app.services.chat import ChatService
from app.services.conversation import ConversationService
from app.services.cost import CostCalculatorService
from app.services.idempotency import IdempotencyService

if TYPE_CHECKING:
    RedisClient = Redis[str]
else:
    RedisClient = Redis

# HTTP Bearer authentication scheme for OpenAPI documentation
bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Bearer token authentication using raw API key.",
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide transactional async database session."""
    async for session in get_async_session():
        yield session


async def get_redis() -> AsyncGenerator[RedisClient, None]:
    """Provide async Redis client."""
    client = get_redis_client()
    try:
        yield client
    finally:
        await client.close()


async def get_current_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> APIKey:
    """Validate Bearer API key via HMAC-SHA-256 hash lookup and return authenticated tenant."""
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Missing or invalid Authorization header.")

    raw_key = credentials.credentials.strip()
    if not raw_key:
        raise UnauthorizedError("Missing or invalid Authorization header.")

    key_hash = hash_api_key(raw_key, settings.api_key_secret)
    api_key_repo = APIKeyRepository(session)
    api_key = await api_key_repo.get_by_key_hash(key_hash)

    if api_key is None or not api_key.is_active:
        raise UnauthorizedError("Invalid or inactive API key.")

    return api_key


def get_llm_provider() -> LLMProvider:
    """Provide LLMProvider instance (defaults to OpenAIProvider, or MockLLMProvider if configured)."""
    if settings.llm_provider.lower() == "mock":
        return MockLLMProvider()
    return OpenAIProvider()


def get_cost_calculator() -> CostCalculatorService:
    """Provide CostCalculatorService instance."""
    return CostCalculatorService()


def get_idempotency_service(
    redis: RedisClient = Depends(get_redis),
) -> IdempotencyService:
    """Provide IdempotencyService instance."""
    return IdempotencyService(redis)


def get_conversation_service(
    session: AsyncSession = Depends(get_db),
) -> ConversationService:
    """Dependency factory providing configured ConversationService instance."""
    conv_repo = ConversationRepository(session)
    msg_repo = MessageRepository(session)
    return ConversationService(conv_repo, msg_repo)


def get_chat_service(
    session: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    llm_provider: LLMProvider = Depends(get_llm_provider),
) -> ChatService:
    """Dependency factory providing configured ChatService instance."""
    conv_repo = ConversationRepository(session)
    msg_repo = MessageRepository(session)
    llm_req_repo = LLMRequestRepository(session)
    cost_calc = CostCalculatorService()
    idempotency = IdempotencyService(redis)
    return ChatService(
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        llm_request_repo=llm_req_repo,
        llm_provider=llm_provider,
        cost_calculator=cost_calc,
        idempotency_service=idempotency,
    )
