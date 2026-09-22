"""Phase 52 shared formatting/validation helpers for reports and documents."""
from __future__ import annotations
from datetime import date, datetime


def validate_report_period(start: str, end: str) -> tuple[str, str]:
    """Validate ISO report dates and reject an inverted period."""
    try:
        a = datetime.strptime(start.strip(), "%Y-%m-%d").date()
        b = datetime.strptime(end.strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise ValueError("Dates must use YYYY-MM-DD format.") from exc
    if a > b:
        raise ValueError("The 'From' date cannot be later than the 'To' date.")
    return a.isoformat(), b.isoformat()


def report_filename(report_type: str, start: str, end: str) -> str:
    """Return a safe, descriptive PDF filename."""
    a, b = validate_report_period(start, end)
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(report_type))
    return f"BKPOS_{safe}_{a}_to_{b}.pdf"


def empty_report_message(title: str) -> str:
    return f"No records were found for {title} in the selected period."
