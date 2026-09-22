"""BKPOS Phase 61 — startup/shutdown lifecycle hardening."""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from core.config import DATA_DIR
from core.logger import logger

LIFECYCLE_DIR = Path(DATA_DIR) / "runtime"
STATE_PATH = LIFECYCLE_DIR / "lifecycle_state.json"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _write_state(state: dict[str, Any]) -> None:
    LIFECYCLE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp, STATE_PATH)


def read_lifecycle_state() -> dict[str, Any]:
    """Read the last lifecycle state without changing it."""
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}


def startup_runtime() -> dict[str, Any]:
    """Record a startup and report whether the previous run was clean."""
    previous = read_lifecycle_state()
    previous_clean = previous.get("status") == "clean_shutdown"
    state = {
        "status": "running",
        "started_at": _now(),
        "pid": os.getpid(),
        "packaged": bool(getattr(sys, "frozen", False)),
        "previous_status": previous.get("status", "unknown"),
        "previous_clean": previous_clean,
    }
    try:
        _write_state(state)
    except OSError as exc:
        logger.warning("Could not write BKPOS startup lifecycle state: %s", exc)
    else:
        if not previous_clean and previous:
            logger.warning("BKPOS previous run did not record a clean shutdown")
        logger.info("BKPOS startup recorded pid=%s", os.getpid())
    return state


def clean_shutdown(reason: str = "normal_exit") -> dict[str, Any]:
    """Record a clean shutdown after the application has fully exited."""
    state = read_lifecycle_state()
    state.update({
        "status": "clean_shutdown",
        "shutdown_at": _now(),
        "shutdown_reason": str(reason),
    })
    try:
        _write_state(state)
    except OSError as exc:
        logger.warning("Could not write BKPOS shutdown lifecycle state: %s", exc)
    else:
        logger.info("BKPOS clean shutdown recorded reason=%s", reason)
    return state


def install_exception_hook() -> None:
    """Log uncaught exceptions while deliberately leaving runtime state as running."""
    def _hook(exc_type, exc_value, exc_tb):
        logger.critical(
            "BKPOS uncaught exception: %s",
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb)).rstrip(),
        )
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook


def lifecycle_status() -> dict[str, Any]:
    """Return compact lifecycle diagnostics for support tooling."""
    state = read_lifecycle_state()
    return {
        "ok": bool(state),
        "status": state.get("status", "unknown"),
        "started_at": state.get("started_at", ""),
        "shutdown_at": state.get("shutdown_at", ""),
        "previous_clean": state.get("previous_clean"),
        "pid": state.get("pid"),
        "path": str(STATE_PATH),
    }
