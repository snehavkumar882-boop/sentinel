"""Integration tests for health check endpoints and preflight validation."""

from fastapi.testclient import TestClient
from src.api.health import perform_system_health_check


def test_health_check_function() -> None:
    """Verify internal system health check function execution."""
    health = perform_system_health_check()
    assert health.status in ("healthy", "degraded")
    assert health.app_name == "SENTINEL"
    assert len(health.components) >= 2


def test_health_check_endpoint(client: TestClient) -> None:
    """Verify GET /api/v1/health returns 200 OK and valid health payload."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert data["app_name"] == "SENTINEL"
    assert "version" in data
    assert "components" in data
    assert isinstance(data["components"], list)
