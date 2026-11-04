"""Health check used by Docker, Render and monitoring."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Report that the service is up."""
    return {"status": "ok"}
