"""Repository for APIKey persistence and HMAC authentication lookups."""

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import APIKey
from app.repositories.base import BaseRepository


class APIKeyRepository(BaseRepository[APIKey]):
    """Data access layer for API keys."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, APIKey)

    async def get_by_key_hash(self, key_hash: str) -> APIKey | None:
        """Fetch active API key record by its HMAC-SHA-256 hash."""
        stmt = select(APIKey).where(
            APIKey.key_hash == key_hash,
            APIKey.is_active.is_(True),
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_id(self, api_key_id: uuid.UUID) -> APIKey | None:
        """Fetch API key by primary key ID."""
        stmt = select(APIKey).where(APIKey.id == api_key_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def update_last_used(self, api_key_id: uuid.UUID) -> None:
        """Update last_used_at timestamp for the designated API key."""
        stmt = update(APIKey).where(APIKey.id == api_key_id).values(last_used_at=func.now())
        await self.session.execute(stmt)
        await self.session.commit()
