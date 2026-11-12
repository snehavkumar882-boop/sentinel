"""Health check router and verification models for SENTINEL API."""

import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Literal
from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from src.config.settings import get_settings

router = APIRouter(tags=["Health"])


class ComponentStatus(BaseModel):
    """Status description for an individual subsystem component."""

    name: str
    status: Literal["healthy", "degraded", "unhealthy"]
    details: str


class HealthCheckResponse(BaseModel):
    """Structured response for the platform health verification."""

    status: Literal["healthy", "degraded", "unhealthy"]
    app_name: str
    version: str
    environment: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    python_version: str
    components: List[ComponentStatus]


def perform_system_health_check() -> HealthCheckResponse:
    """Execute non-destructive system diagnostics to verify runtime readiness."""
    settings = get_settings()

    components: List[ComponentStatus] = []

    # 1. Configuration check
    try:
        assert settings.APP_NAME is not None
        components.append(
            ComponentStatus(
                name="configuration",
                status="healthy",
                details=f"Settings loaded for environment '{settings.ENVIRONMENT}'",
            )
        )
    except Exception as exc:
        components.append(
            ComponentStatus(
                name="configuration",
                status="unhealthy",
                details=f"Configuration error: {exc}",
            )
        )

    # 2. File system data directory check
    data_dir = settings.DATA_DIR
    if data_dir.exists() and os.access(data_dir, os.W_OK):
        components.append(
            ComponentStatus(
                name="storage_data_dir",
                status="healthy",
                details=f"Writable data directory available at: {data_dir}",
            )
        )
    else:
        # Create it if it doesn't exist yet
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
            components.append(
                ComponentStatus(
                    name="storage_data_dir",
                    status="healthy",
                    details=f"Initialized data directory at: {data_dir}",
                )
            )
        except Exception as exc:
            components.append(
                ComponentStatus(
                    name="storage_data_dir",
                    status="degraded",
                    details=f"Unable to access or create {data_dir}: {exc}",
                )
            )

    # Determine overall status
    overall_status: Literal["healthy", "degraded", "unhealthy"] = "healthy"
    for comp in components:
        if comp.status == "unhealthy":
            overall_status = "unhealthy"
            break
        elif comp.status == "degraded":
            overall_status = "degraded"

    return HealthCheckResponse(
        status=overall_status,
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        components=components,
    )


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Platform Health Check",
    description="Returns runtime health, component readiness, and configuration metadata.",
)
async def get_health() -> HealthCheckResponse:
    """Endpoint returning system health and dependency checks."""
    return perform_system_health_check()
