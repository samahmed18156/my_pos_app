"""BKPOS Phase 59 — safe runtime logging diagnostics."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from core.logger import LOG_PATH, logger

_SECRET_KEYS = {"password", "passwd", "secret", "token", "api_key", "apikey"}


def redact_mapping(values: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow redacted copy suitable for diagnostic logging."""
    return {
        str(key): ("***REDACTED***" if str(key).lower() in _SECRET_KEYS else value)
        for key, value in values.items()
    }


def logging_status() -> dict[str, Any]:
    """Report whether BKPOS has a writable file logger without changing data."""
    handlers = list(logger.handlers)
    file_handlers = [h for h in handlers if isinstance(h, logging.FileHandler)]
    path = Path(LOG_PATH) if LOG_PATH else None
    writable = bool(file_handlers and path and path.parent.exists() and os.access(path.parent, os.W_OK))
    return {
        "ok": bool(file_handlers),
        "file_logging": bool(file_handlers),
        "writable": writable,
        "path": str(path) if path else "",
        "handler_count": len(handlers),
    }


def log_event(message: str, level: int = logging.INFO, **context: Any) -> None:
    """Write a structured one-line event with common secret fields redacted."""
    safe = redact_mapping(context)
    suffix = " " + " ".join(f"{k}={v!r}" for k, v in safe.items()) if safe else ""
    logger.log(level, "%s%s", message, suffix)
