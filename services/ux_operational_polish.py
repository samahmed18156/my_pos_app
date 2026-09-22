"""Phase 51: small, safe UX/operational helpers."""
from __future__ import annotations

from datetime import datetime

APP_NAME = "BKPOS"


def app_window_title(store_name: str = "") -> str:
    """Return one consistent application title."""
    store_name = (store_name or "").strip()
    return f"{APP_NAME} - {store_name}" if store_name else APP_NAME


def format_operator_status(full_name: str = "", role: str = "") -> str:
    """Return a compact, human-readable operator status string."""
    name = (full_name or "Operator").strip()
    role = (role or "").strip()
    return f"{name}  •  {role}" if role else name


def format_last_refresh(value: datetime | None = None) -> str:
    """Return a consistent refresh timestamp for status areas."""
    value = value or datetime.now()
    return f"Last refreshed: {value.strftime('%Y-%m-%d %H:%M:%S')}"
