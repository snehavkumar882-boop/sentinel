"""Global pytest fixtures and test configuration for SENTINEL."""

import os
from typing import Generator
import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.config.settings import Settings, get_settings


@pytest.fixture(autouse=True)
def test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure safe testing environment variables for every test."""
    monkeypatch.setenv("SENTINEL_ENVIRONMENT", "testing")
    monkeypatch.setenv("SENTINEL_DEBUG", "true")
    monkeypatch.setenv("SENTINEL_LOG_LEVEL", "DEBUG")
    # Invalidate cache so fresh settings are used
    get_settings.cache_clear()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Provide a FastAPI test client instance."""
    with TestClient(app) as test_client:
        yield test_client
