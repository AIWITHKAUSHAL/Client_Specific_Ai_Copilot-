"""Logging configuration for the Operations Copilot.

Two handlers are configured:

* a **file handler** writing structured, one-line-per-query records to
  ``logs/copilot.log`` (created on demand, so the app never crashes because
  the directory is missing);
* an optional **console handler** for interactive debugging.

The prototype uses Python's standard library only.  In production the same
records are shipped to a log aggregator (CloudWatch / ELK / Splunk / Datadog)
- see docs/production-readiness.md.
"""

from __future__ import annotations

import logging
import sys
from logging import Logger
from pathlib import Path

from core.config import LOG_FILE, LOG_LEVEL

_CONFIGURED = False

FILE_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
CONSOLE_FORMAT = "%(levelname)-7s | %(message)s"


def _ensure_log_directory(log_file: Path) -> bool:
    """Create the log directory if needed.

    Returns ``True`` when file logging is possible.  A read-only filesystem
    (common in hardened containers) must never take the application down, so
    failures degrade to console-only logging.
    """
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        return True
    except OSError:  # pragma: no cover - depends on filesystem permissions
        return False


def configure_logging(console: bool = False, level: str | None = None) -> Logger:
    """Configure and return the root copilot logger (idempotent)."""
    global _CONFIGURED

    logger = logging.getLogger("copilot")
    if _CONFIGURED:
        return logger

    logger.setLevel(getattr(logging, level or LOG_LEVEL, logging.INFO))
    logger.propagate = False

    if _ensure_log_directory(LOG_FILE):
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(FILE_FORMAT))
        logger.addHandler(file_handler)

    if console:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT))
        logger.addHandler(stream_handler)

    if not logger.handlers:  # pragma: no cover - defensive fallback
        logger.addHandler(logging.NullHandler())

    _CONFIGURED = True
    return logger


def get_logger(name: str = "copilot") -> Logger:
    """Return a child logger, configuring logging on first use."""
    configure_logging()
    return logging.getLogger(name if name.startswith("copilot") else f"copilot.{name}")
