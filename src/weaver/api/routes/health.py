"""
Health check endpoints.
"""

from fastapi import APIRouter
from datetime import datetime
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: datetime
    version: str


@router.get("/", response_model=HealthResponse)
async def health_check():
    """
    Basic health check endpoint.
    
    Returns:
        Health status
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="1.0.0"
    )


@router.get("/ready", response_model=HealthResponse)
async def readiness_check():
    """
    Readiness check endpoint.
    Verifies that the service is ready to accept requests.
    
    Returns:
        Readiness status
    """
    # TODO: Add checks for dependencies (e.g., can load stages, etc.)
    return HealthResponse(
        status="ready",
        timestamp=datetime.utcnow(),
        version="1.0.0"
    )
