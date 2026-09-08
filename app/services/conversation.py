"""Service implementing conversation business logic, validation, and tenant isolation."""

import uuid

from app.core.exceptions import ConversationNotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.metrics import metrics
from app.repositories.conversation import ConversationRepository
from app.repositories.message import MessageRepository
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetailResponse,
    ConversationResponse,
    PaginatedConversationsResponse,
    UsageSummaryResponse,
)
from app.schemas.message import MessageResponse

logger = get_logger(__name__)


class ConversationService:
    """Encapsulates business operations on conversations, ensuring tenant ownership enforcement."""

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
    ) -> None:
        self.conversation_repo = conversation_repo
        self.message_repo = message_repo

    async def create_conversation(
        self,
        api_key_id: uuid.UUID,
        data: ConversationCreate,
    ) -> ConversationResponse:
        """Create a new conversation belonging to the authenticated tenant."""
        title = data.title.strip()
        if not title:
            raise ValidationError("Conversation title cannot be empty.")

        conversation = await self.conversation_repo.create(
            api_key_id=api_key_id,
            title=title,
            system_prompt=data.system_prompt.strip() if data.system_prompt else None,
        )
        metrics.record_conversation_op("create")
        metrics.record_db_op("create_conversation", "success")
        logger.info("conversation_created", conversation_id=str(conversation.id))
        return ConversationResponse.model_validate(conversation)

    async def list_conversations(
        self,
        api_key_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedConversationsResponse:
        """Retrieve paginated active conversations belonging to the authenticated tenant."""
        if page < 1:
            raise ValidationError("Page number must be greater than or equal to 1.")
        if page_size < 1 or page_size > 100:
            raise ValidationError("Page size must be between 1 and 100.")

        items, total = await self.conversation_repo.list_by_api_key(
            api_key_id=api_key_id,
            page=page,
            page_size=page_size,
        )
        metrics.record_conversation_op("list")
        metrics.record_db_op("list_conversations", "success")

        response_items = [ConversationResponse.model_validate(item) for item in items]
        return PaginatedConversationsResponse.create(
            items=response_items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_conversation(
        self,
        conversation_id: uuid.UUID,
        api_key_id: uuid.UUID,
    ) -> ConversationDetailResponse:
        """Retrieve conversation details, message history, and token/cost summary.

        Raises ConversationNotFoundError if conversation does not exist, was soft-deleted,
        or belongs to another tenant.
        """
        conversation = await self.conversation_repo.get_by_id(
            conversation_id=conversation_id,
            api_key_id=api_key_id,
            include_deleted=False,
        )
        if conversation is None:
            metrics.record_db_op("get_conversation", "not_found")
            raise ConversationNotFoundError(f"Conversation with ID '{conversation_id}' not found.")

        messages = await self.message_repo.list_by_conversation(conversation_id)
        stats = await self.conversation_repo.get_usage_stats(conversation_id)
        metrics.record_conversation_op("get")
        metrics.record_db_op("get_conversation", "success")

        return ConversationDetailResponse(
            id=conversation.id,
            title=conversation.title,
            system_prompt=conversation.system_prompt,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            messages=[MessageResponse.model_validate(msg) for msg in messages],
            usage_summary=UsageSummaryResponse(**stats),
        )

    async def delete_conversation(
        self,
        conversation_id: uuid.UUID,
        api_key_id: uuid.UUID,
    ) -> None:
        """Soft-delete an active conversation owned by the caller.

        Raises ConversationNotFoundError if conversation does not exist, was already deleted,
        or belongs to another tenant.
        """
        deleted = await self.conversation_repo.soft_delete(
            conversation_id=conversation_id,
            api_key_id=api_key_id,
        )
        if not deleted:
            metrics.record_db_op("delete_conversation", "not_found")
            raise ConversationNotFoundError(f"Conversation with ID '{conversation_id}' not found.")

        metrics.record_conversation_op("delete")
        metrics.record_db_op("delete_conversation", "success")
        logger.info("conversation_deleted", conversation_id=str(conversation_id))
