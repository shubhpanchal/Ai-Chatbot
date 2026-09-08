"""Generic async base repository with SQLAlchemy 2.0 session handling."""

from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base generic repository encapsulating common database session interactions."""

    def __init__(self, session: AsyncSession, model: type[ModelType]) -> None:
        self.session = session
        self.model = model
