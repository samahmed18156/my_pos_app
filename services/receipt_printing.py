"""Production-safe receipt printing helpers for BKPOS."""
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class ReceiptPrintResult:
    success: bool
    status: str
    message: str
    printer_name: str


def configured_printer_name(default="POS-80C"):
    """Return the configured receipt printer without requiring Windows APIs."""
    return os.environ.get("BKPOS_RECEIPT_PRINTER", "").strip() or default


def printer_diagnostics(printer_name=None):
    """Return operator-friendly, read-only printer diagnostics."""
    from receipt_printer import get_default_printer, get_installed_printers, win32print
    name = printer_name or configured_printer_name()
    if win32print is None:
        return {"ok": False, "status": "UNAVAILABLE", "printer": name,
                "default_printer": None, "installed": [],
                "message": "Windows printing support is unavailable (pywin32 is not installed)."}
    installed = get_installed_printers()
    if name not in installed:
        default = get_default_printer()
        hint = f" Windows default printer is '{default}'." if default else ""
        return {"ok": False, "status": "NOT_FOUND", "printer": name,
                "default_printer": default, "installed": installed,
                "message": f"Receipt printer '{name}' is not available in Windows.{hint}"}
    return {"ok": True, "status": "READY", "printer": name,
            "default_printer": get_default_printer(), "installed": installed,
            "message": f"Receipt printer '{name}' is ready."}


def safe_print_receipt(**kwargs):
    """Print once and convert hardware errors into a safe result.

    The caller can show the message and retain the completed sale; this function
    deliberately does not retry automatically because duplicate paper receipts
    are worse than a missed print.
    """
    name = kwargs.get("printer_name") or configured_printer_name()
    kwargs["printer_name"] = name
    try:
        from receipt_printer import print_receipt
        print_receipt(**kwargs)
        return ReceiptPrintResult(True, "PRINTED", "Receipt printed successfully.", name)
    except Exception as exc:
        return ReceiptPrintResult(False, "FAILED", str(exc), name)
