"""BKPOS Phase 70 — consistent operator-facing error messages."""
from __future__ import annotations

MESSAGES = {
    "printer": "Sale completed, but the receipt could not be printed. Resolve the printer problem and reprint from History.",
    "database": "BKPOS could not safely access its database. Stop processing and run Health Check before continuing.",
    "backup": "The backup could not be verified. Do not rely on it for recovery; create another backup after resolving the problem.",
    "duplicate": "This transaction was already completed. No second transaction was created.",
    "permission": "You do not have permission to perform this action.",
    "shift_open": "This cashier already has an open shift. Close the current shift before opening another one.",
    "cashup_variance": "The cash-up has a variance. Enter a reason and follow the approval procedure before closing.",
}


def operator_message(code: str, fallback: str = "The operation could not be completed safely.") -> str:
    return MESSAGES.get(str(code).strip().lower(), fallback)


def safe_exception_message(exc: BaseException, fallback: str = "The operation could not be completed safely.") -> str:
    """Return a useful message without exposing a traceback to the operator."""
    text = str(exc).strip()
    return text if text else fallback
