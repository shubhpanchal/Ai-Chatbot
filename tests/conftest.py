"""Global Pytest fixtures and configuration."""

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import generate_raw_api_key, hash_api_key
from app.main import app
from app.models.api_key import APIKey


@pytest.fixture
async def async_client(test_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    """Provide an asynchronous HTTP client with overridden DB dependency for testing."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def test_engine() -> AsyncIterator[AsyncEngine]:
    """Provide an isolated async database engine for pytest event loops."""
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Provide an isolated database session for testing."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
async def primary_api_key(db_session: AsyncSession) -> tuple[APIKey, str, dict[str, str]]:
    """Create and return a primary active tenant API key with auth headers."""
    raw_key = generate_raw_api_key(prefix="ak_test_primary")
    key_hash = hash_api_key(raw_key, settings.api_key_secret)
    api_key = APIKey(
        id=uuid.uuid4(),
        name="Primary Test Tenant",
        key_hash=key_hash,
        is_active=True,
    )
    db_session.add(api_key)
    await db_session.commit()
    await db_session.refresh(api_key)

    headers = {"Authorization": f"Bearer {raw_key}"}
    return api_key, raw_key, headers


@pytest.fixture
async def secondary_api_key(db_session: AsyncSession) -> tuple[APIKey, str, dict[str, str]]:
    """Create and return a secondary active tenant API key for cross-tenant testing."""
    raw_key = generate_raw_api_key(prefix="ak_test_secondary")
    key_hash = hash_api_key(raw_key, settings.api_key_secret)
    api_key = APIKey(
        id=uuid.uuid4(),
        name="Secondary Test Tenant",
        key_hash=key_hash,
        is_active=True,
    )
    db_session.add(api_key)
    await db_session.commit()
    await db_session.refresh(api_key)

    headers = {"Authorization": f"Bearer {raw_key}"}
    return api_key, raw_key, headers


@pytest.fixture
async def inactive_api_key(db_session: AsyncSession) -> tuple[APIKey, str, dict[str, str]]:
    """Create and return a deactivated API key for 401 Unauthorized testing."""
    raw_key = generate_raw_api_key(prefix="ak_test_inactive")
    key_hash = hash_api_key(raw_key, settings.api_key_secret)
    api_key = APIKey(
        id=uuid.uuid4(),
        name="Inactive Test Tenant",
        key_hash=key_hash,
        is_active=False,
    )
    db_session.add(api_key)
    await db_session.commit()
    await db_session.refresh(api_key)

    headers = {"Authorization": f"Bearer {raw_key}"}
    return api_key, raw_key, headers
