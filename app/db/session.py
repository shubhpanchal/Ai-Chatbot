"""SQLAlchemy 2.0 async engine and sessionmaker configuration."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# Configure async engine with resilient connection pooling and timeouts
engine: AsyncEngine = create_async_engine(
    url=settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle_seconds,
    pool_pre_ping=True,
    echo=settings.debug,
    connect_args={
        "command_timeout": settings.db_command_timeout_seconds,
        "timeout": settings.db_connect_timeout_seconds,
    },
)

# Async session factory
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing transactional async database sessions."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Gracefully close all pooled database connections on application shutdown."""
    await engine.dispose()
