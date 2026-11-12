"""Unit tests for the Settings and configuration system."""

import pytest
from pydantic import ValidationError

from src.config.settings import Settings, get_settings


def test_default_settings_instantiation() -> None:
    """Verify that default settings instantiate with expected valid attributes."""
    settings = Settings()
    assert settings.APP_NAME == "SENTINEL"
    assert settings.APP_VERSION == "0.1.0"
    assert settings.PORT == 8000
    assert settings.ANOMALY_ZSCORE_THRESHOLD == 3.0
    assert settings.ISOLATION_FOREST_CONTAMINATION == 0.05
    assert settings.RAG_TOP_K == 5


def test_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify environment variables with SENTINEL_ prefix correctly override defaults."""
    monkeypatch.setenv("SENTINEL_APP_NAME", "SENTINEL-OVERRIDE")
    monkeypatch.setenv("SENTINEL_PORT", "9090")
    monkeypatch.setenv("SENTINEL_DEBUG", "true")
    monkeypatch.setenv("SENTINEL_ANOMALY_ZSCORE_THRESHOLD", "4.5")

    settings = Settings()
    assert settings.APP_NAME == "SENTINEL-OVERRIDE"
    assert settings.PORT == 9090
    assert settings.DEBUG is True
    assert settings.ANOMALY_ZSCORE_THRESHOLD == 4.5


def test_invalid_settings_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that out-of-bound or invalid configuration raises validation errors."""
    monkeypatch.setenv("SENTINEL_ANOMALY_ZSCORE_THRESHOLD", "0.5")  # ge is 1.0
    with pytest.raises(ValidationError):
        Settings()


def test_get_settings_caching() -> None:
    """Verify that get_settings() returns a cached singleton instance."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
