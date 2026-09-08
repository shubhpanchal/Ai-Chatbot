"""Initial database schema for API keys, conversations, messages, and LLM requests.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-08 11:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create api_keys table
    op.create_table(
        "api_keys",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_keys")),
    )
    op.create_index(
        op.f("ix_api_keys_key_hash"),
        "api_keys",
        ["key_hash"],
        unique=True,
    )

    # 2. Create conversations table
    op.create_table(
        "conversations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["api_key_id"],
            ["api_keys.id"],
            name=op.f("fk_conversations_api_key_id_api_keys"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
    )
    op.create_index(
        "idx_conversations_api_key_created",
        "conversations",
        ["api_key_id", "created_at"],
        unique=False,
        postgresql_using="btree",
    )
    op.create_index(
        "idx_conversations_api_key_deleted",
        "conversations",
        ["api_key_id", "deleted_at"],
        unique=False,
        postgresql_using="btree",
    )
    op.create_index(
        op.f("ix_conversations_api_key_id"),
        "conversations",
        ["api_key_id"],
        unique=False,
    )

    # 3. Create messages table
    op.create_table(
        "messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_messages_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
    )
    op.create_index(
        "idx_messages_conv_created",
        "messages",
        ["conversation_id", "created_at"],
        unique=False,
        postgresql_using="btree",
    )
    op.create_index(
        op.f("ix_messages_conversation_id"),
        "messages",
        ["conversation_id"],
        unique=False,
    )

    # 4. Create llm_requests table
    op.create_table(
        "llm_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "estimated_cost",
            sa.Numeric(precision=10, scale=6),
            nullable=False,
            server_default=sa.text("0.000000"),
        ),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'success'"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_llm_requests_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name=op.f("fk_llm_requests_message_id_messages"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_requests")),
    )
    op.create_index(
        op.f("ix_llm_requests_conversation_id"),
        "llm_requests",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_requests_created_at"),
        "llm_requests",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_requests_message_id"),
        "llm_requests",
        ["message_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_llm_requests_message_id"), table_name="llm_requests")
    op.drop_index(op.f("ix_llm_requests_created_at"), table_name="llm_requests")
    op.drop_index(op.f("ix_llm_requests_conversation_id"), table_name="llm_requests")
    op.drop_table("llm_requests")

    op.drop_index(op.f("ix_messages_conversation_id"), table_name="messages")
    op.drop_index("idx_messages_conv_created", table_name="messages")
    op.drop_table("messages")

    op.drop_index(op.f("ix_conversations_api_key_id"), table_name="conversations")
    op.drop_index("idx_conversations_api_key_deleted", table_name="conversations")
    op.drop_index("idx_conversations_api_key_created", table_name="conversations")
    op.drop_table("conversations")

    op.drop_index(op.f("ix_api_keys_key_hash"), table_name="api_keys")
    op.drop_table("api_keys")
