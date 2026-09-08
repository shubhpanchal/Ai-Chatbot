"""Health and liveness check routes."""

from fastapi import APIRouter, status

from app.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness Probe",
    description="Returns liveness status of the API process.",
)
async def get_health() -> HealthResponse:
    """Return application liveness status."""
    return HealthResponse(status="healthy")
