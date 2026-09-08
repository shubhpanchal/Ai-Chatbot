"""FastAPI dependency providers for authentication, database sessions, and services."""

from collections.abc import AsyncGenerator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.security import hash_api_key
from app.db.session import get_async_session
from app.models.api_key import APIKey
from app.repositories.api_key import APIKeyRepository
from app.repositories.conversation import ConversationRepository
from app.repositories.message import MessageRepository
from app.services.conversation import ConversationService

# HTTP Bearer authentication scheme for OpenAPI documentation
bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Bearer token authentication using raw API key.",
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide transactional async database session."""
    async for session in get_async_session():
        yield session


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


def get_conversation_service(
    session: AsyncSession = Depends(get_db),
) -> ConversationService:
    """Dependency factory providing configured ConversationService instance."""
    conv_repo = ConversationRepository(session)
    msg_repo = MessageRepository(session)
    return ConversationService(conv_repo, msg_repo)
