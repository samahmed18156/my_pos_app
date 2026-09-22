"""BKPOS production-safe logging.

Logs are kept in a user-writable location for packaged builds so BKPOS does
not require administrator rights just to record diagnostics.  Source-mode
logging remains project-local for developer convenience.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

APP_NAME = "BKPOS"
LOG_FILENAME = "bkpos.log"


def _log_directory() -> Path:
    if getattr(sys, "frozen", False):
        root = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        if root:
            return Path(root) / APP_NAME / "logs"
        return Path(sys.executable).resolve().parent / "logs"
    return Path(__file__).resolve().parent.parent / "logs"


def _build_logger() -> tuple[logging.Logger, Path]:
    logger = logging.getLogger(APP_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return logger, Path(getattr(logger.handlers[0], "baseFilename", ""))

    directory = _log_directory()
    log_path = directory / LOG_FILENAME
    try:
        directory.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    except (OSError, PermissionError):
        handler = logging.NullHandler()
    logger.addHandler(handler)
    return logger, log_path


# logging.handlers is imported lazily above to keep the module compact.
import logging.handlers  # noqa: E402

logger, LOG_PATH = _build_logger()
