"""Integration tests for database seed script and data verification."""

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import APIKey
from app.models.conversation import Conversation
from app.models.message import Message
from scripts.seed_db import seed_database


@pytest.mark.asyncio
async def test_seed_database_integration(db_session: AsyncSession) -> None:
    """Test that seed_database loads synthetic conversations and messages correctly."""
    seed_file = Path("data/seed/conversations.json")
    assert seed_file.exists()

    custom_key = "ak_test_seed_verification_key_12345"
    await seed_database(
        file_path=seed_file,
        api_key_name="test-seed-runner",
        raw_api_key=custom_key,
        session=db_session,
    )

    # Verify APIKey exists
    stmt_key = select(APIKey).where(APIKey.name == "test-seed-runner")
    res_key = await db_session.execute(stmt_key)
    api_key = res_key.scalar_one_or_none()
    assert api_key is not None

    # Verify total seeded conversations in database
    stmt_all_convs = select(Conversation)
    res_all_convs = await db_session.execute(stmt_all_convs)
    all_conversations = res_all_convs.scalars().all()
    assert len(all_conversations) >= 50

    # Verify Messages exist in database
    stmt_all_msgs = select(Message)
    res_all_msgs = await db_session.execute(stmt_all_msgs)
    all_messages = res_all_msgs.scalars().all()
    assert len(all_messages) >= 100
    assert all_messages[0].role in ["system", "user", "assistant"]
    assert len(all_messages[0].content) > 0
