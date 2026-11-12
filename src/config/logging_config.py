"""Structured application logging configuration for SENTINEL."""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict


class StructuredJsonFormatter(logging.Formatter):
    """JSON log formatter producing machine-readable structured log events."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }

        # Include custom extra metadata if passed
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_entry["data"] = record.extra

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class StandardFormatter(logging.Formatter):
    """Clean, human-readable console formatter for development environments."""

    FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    def __init__(self) -> None:
        super().__init__(fmt=self.FORMAT, datefmt=self.DATE_FORMAT)


def setup_logging(log_level: str = "INFO", json_format: bool = False) -> None:
    """Configure the root logger with the specified level and format.

    Args:
        log_level: Desired log level string (e.g. 'DEBUG', 'INFO', 'WARNING', 'ERROR').
        json_format: If True, outputs JSON formatted log lines; otherwise uses standard text.
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers to prevent duplicate lines
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)

    if json_format:
        handler.setFormatter(StructuredJsonFormatter())
    else:
        handler.setFormatter(StandardFormatter())

    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Convenience factory function to obtain a configured named logger."""
    return logging.getLogger(name)
