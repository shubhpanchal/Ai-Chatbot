"""Aggregated API v1 router."""

from fastapi import APIRouter

from app.api.v1.conversations import router as conversations_router
from app.api.v1.health import router as health_router
from app.api.v1.messages import router as messages_router

api_v1_router = APIRouter()

# Include health routes
api_v1_router.include_router(health_router)

# Include conversations routes
api_v1_router.include_router(conversations_router)

# Include messages routes
api_v1_router.include_router(messages_router)
