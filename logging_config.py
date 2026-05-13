"""
Structured logging configuration for production environments.

Features:
- JSON-formatted logs for log aggregators (ELK, CloudWatch, Datadog)
- Human-readable text format for development
- Log rotation (10 MB × 5 backups)
- Correlation IDs per pipeline run
- Separate console and file handlers
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Optional

# Context variable for correlation ID (thread-safe)
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="no-correlation")


def get_correlation_id() -> str:
    """Return the current correlation ID."""
    return _correlation_id.get()


def set_correlation_id(cid: Optional[str] = None) -> str:
    """Set (or generate) a new correlation ID and return it."""
    new_id = cid or uuid.uuid4().hex[:12]
    _correlation_id.set(new_id)
    return new_id


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for production."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "correlation_id": get_correlation_id(),
        }

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
            }

        # Include extra fields if present
        for key in ("candidate_id", "step", "duration_ms", "extra"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        return json.dumps(log_entry, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable formatter for development."""

    FORMAT = "%(asctime)s │ %(levelname)-8s │ %(name)-25s │ %(message)s"

    def __init__(self):
        super().__init__(self.FORMAT, datefmt="%H:%M:%S")


def setup_logging(
    level: str = "INFO",
    log_format: str = "json",
    logs_dir: str = "./logs",
) -> None:
    """
    Configure application-wide logging.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: 'json' for production, 'text' for development.
        logs_dir: Directory for log files.
    """
    os.makedirs(logs_dir, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Clear existing handlers to avoid duplicates on reload
    root_logger.handlers.clear()

    # ── Console handler (always human-readable) ───────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    console_handler.setFormatter(TextFormatter())
    root_logger.addHandler(console_handler)

    # ── File handler (structured JSON, rotated) ───────────────────
    log_file = os.path.join(logs_dir, "app.log")
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)

    if log_format == "json":
        file_handler.setFormatter(JSONFormatter())
    else:
        file_handler.setFormatter(TextFormatter())

    root_logger.addHandler(file_handler)

    # Quieten noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "openai", "anthropic", "langchain"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging configured: level=%s, format=%s, file=%s", level, log_format, log_file
    )
