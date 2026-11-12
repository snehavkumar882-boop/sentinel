"""Unit tests for structured logging."""

import json
import logging
from src.config.logging_config import (
    StructuredJsonFormatter,
    StandardFormatter,
    get_logger,
    setup_logging,
)


def test_standard_formatter() -> None:
    """Verify standard text formatter produces formatted output."""
    formatter = StandardFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    assert "INFO" in formatted
    assert "test_logger:42" in formatted
    assert "Test message" in formatted


def test_structured_json_formatter() -> None:
    """Verify structured JSON formatter produces valid parseable JSON."""
    formatter = StructuredJsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.ERROR,
        pathname="test.py",
        lineno=10,
        msg="Error event occurred",
        args=(),
        exc_info=None,
    )
    record.extra = {"incident_id": "INC-001", "service": "checkout"}  # type: ignore

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "ERROR"
    assert parsed["logger"] == "test_logger"
    assert parsed["message"] == "Error event occurred"
    assert parsed["data"]["incident_id"] == "INC-001"
    assert parsed["data"]["service"] == "checkout"


def test_setup_logging_and_get_logger() -> None:
    """Verify logger setup runs without errors and retrieves named loggers."""
    setup_logging(log_level="DEBUG", json_format=False)
    logger = get_logger("sentinel.test")
    assert logger.name == "sentinel.test"
    assert logger.isEnabledFor(logging.DEBUG)
