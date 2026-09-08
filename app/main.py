"""FastAPI application factory and entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.health import router as health_router
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.middleware.error_handler import register_error_handlers
from app.middleware.request_logging import RequestLoggingMiddleware

# Initialize structured logging configuration
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan context manager for startup and shutdown hooks."""
    logger.info(
        "application_startup",
        app_name=settings.app_name,
        env=settings.app_env,
        version="0.1.0",
    )
    yield
    logger.info("application_shutdown", app_name=settings.app_name)


def create_application() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title=settings.app_name,
        description="Production-grade AI Chat API with PostgreSQL, Redis, and OpenAI.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # 1. Request logging & correlation middleware (outermost application layer)
    app.add_middleware(RequestLoggingMiddleware)

    # 2. CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 3. Centralized exception handlers
    register_error_handlers(app)

    # 4. Root-level health & readiness probes (/health, /ready, /metrics)
    app.include_router(health_router)

    # 5. Versioned API routes (/api/v1/...)
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    @app.get("/", include_in_schema=False)
    async def root() -> JSONResponse:
        """Root endpoint providing service metadata and documentation links."""
        return JSONResponse(
            content={
                "name": settings.app_name,
                "environment": settings.app_env,
                "version": "0.1.0",
                "docs": "/docs",
                "health": "/health",
                "ready": "/ready",
                "metrics": "/metrics",
            }
        )

    return app


app = create_application()
