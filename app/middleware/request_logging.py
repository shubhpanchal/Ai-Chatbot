"""Request correlation and structured access logging middleware."""

from __future__ import annotations

import time
import uuid

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.logging import get_logger
from app.core.metrics import metrics

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for assigning request IDs, binding structlog contextvars, and logging access."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 1. Resolve or generate request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        # Store in request state for downstream handlers
        request.state.request_id = request_id

        # Bind request_id to structlog contextvars for automatic inclusion in all logs
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start_time = time.perf_counter()
        client_ip = request.client.host if request.client else None

        try:
            response = await call_next(request)
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Attach X-Request-ID and X-Response-Time headers to response
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{latency_ms:.2f}ms"

            # Determine route template for low-cardinality metric tracking
            route_path = request.url.path
            if request.scope.get("route"):
                route_path = getattr(request.scope["route"], "path", request.url.path)

            # Record HTTP metrics
            metrics.record_http_request(
                method=request.method,
                route=route_path,
                status_code=response.status_code,
                duration_ms=latency_ms,
            )

            # Emit structured access log
            logger.info(
                "http_request_finished",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                latency_ms=round(latency_ms, 2),
                client_ip=client_ip,
            )

            return response

        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "http_request_unhandled_exception",
                method=request.method,
                path=request.url.path,
                latency_ms=round(latency_ms, 2),
                client_ip=client_ip,
                error_type=type(exc).__name__,
                error_message=str(exc),
                exc_info=True,
            )
            raise
        finally:
            structlog.contextvars.clear_contextvars()
