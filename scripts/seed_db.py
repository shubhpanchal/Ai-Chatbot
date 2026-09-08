"""Database seed script to load synthetic conversation dataset into PostgreSQL."""

import argparse
import asyncio
import json
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import generate_raw_api_key, hash_api_key
from app.db.session import async_session_factory, engine
from app.models.api_key import APIKey
from app.models.conversation import Conversation
from app.models.message import Message


async def seed_database(
    file_path: Path,
    api_key_name: str = "seed-dev-key",
    raw_api_key: str | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Load conversations and messages from JSON into PostgreSQL transactionally."""
    if not file_path.exists():
        print(f"Error: Seed file not found at {file_path}", file=sys.stderr)
        sys.exit(1)

    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    start_time = time.perf_counter()

    if session is not None:
        await _execute_seeding(session, data, api_key_name, raw_api_key, start_time)
    else:
        async with async_session_factory() as new_session, new_session.begin():
            await _execute_seeding(new_session, data, api_key_name, raw_api_key, start_time)


async def _execute_seeding(
    session: AsyncSession,
    data: list[dict[str, Any]],
    api_key_name: str,
    raw_api_key: str | None,
    start_time: float,
) -> None:
    # 1. Ensure or create target APIKey
    if not raw_api_key:
        raw_api_key = generate_raw_api_key("ak_seed")
        key_hash = hash_api_key(raw_api_key, settings.api_key_secret)
        api_key_record = APIKey(
            name=api_key_name,
            key_hash=key_hash,
            is_active=True,
        )
        session.add(api_key_record)
        await session.flush()
        print(f"Created new Seed API Key: {raw_api_key}")
    else:
        key_hash = hash_api_key(raw_api_key, settings.api_key_secret)
        stmt = select(APIKey).where(APIKey.key_hash == key_hash)
        result = await session.execute(stmt)
        existing_key = result.scalar_one_or_none()
        if existing_key is not None:
            api_key_record = existing_key
        else:
            api_key_record = APIKey(
                name=api_key_name,
                key_hash=key_hash,
                is_active=True,
            )
            session.add(api_key_record)
            await session.flush()
        print(f"Registered provided API Key in database: {raw_api_key}")

    api_key_id = api_key_record.id
    conversations_count = 0
    messages_count = 0

    # 2. Insert Conversations and Messages
    for conv_data in data:
        conv_id = uuid.UUID(conv_data["conversation_id"])

        # Check if conversation already exists
        existing = await session.get(Conversation, conv_id)
        if existing:
            continue

        conv = Conversation(
            id=conv_id,
            api_key_id=api_key_id,
            title=conv_data["title"],
            system_prompt=conv_data.get("system_prompt"),
            created_at=datetime.now(UTC),
        )
        session.add(conv)
        conversations_count += 1

        for msg_data in conv_data.get("messages", []):
            # Parse timestamp if available
            ts = (
                datetime.fromisoformat(msg_data["timestamp"])
                if "timestamp" in msg_data
                else datetime.now(UTC)
            )
            msg = Message(
                conversation_id=conv_id,
                role=msg_data["role"],
                content=msg_data["content"],
                created_at=ts,
            )
            session.add(msg)
            messages_count += 1

    await session.flush()
    elapsed = time.perf_counter() - start_time
    print("--------------------------------------------------")
    print("Database Seeding Completed Successfully!")
    print(f"API Key ID     : {api_key_id}")
    print(f"Conversations  : {conversations_count}")
    print(f"Messages       : {messages_count}")
    print(f"Execution Time : {elapsed:.3f} seconds")
    print("--------------------------------------------------")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed PostgreSQL with synthetic conversations.")
    parser.add_argument(
        "--file",
        type=Path,
        default=Path("data/seed/conversations.json"),
        help="Path to conversations.json file",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Raw API key to associate conversations with (optional)",
    )
    parser.add_argument(
        "--name",
        type=str,
        default="seed-dev-key",
        help="Name for generated API key (default: seed-dev-key)",
    )

    args = parser.parse_args()
    try:
        await seed_database(
            file_path=args.file,
            api_key_name=args.name,
            raw_api_key=args.api_key,
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
