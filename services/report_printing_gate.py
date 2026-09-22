"""BKPOS Phase 78 — reporting and printing production gate.

Headless, read-only checks for the document/report output layer.  Physical
printers and JasperViewer windows are deliberately not required for CI.
"""
from __future__ import annotations

from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPORT_MODULES = (
    "jasper_reports.jasper_receipt",
    "jasper_reports.report_viewer",
    "receipt_printer",
    "services.receipt_printing",
    "document_viewer",
    "reports",
    "history",
    "sales_report",
    "financial_controls",
)
REQUIRED_FILES = (
    "jasper_reports/jasper_receipt.py",
    "jasper_reports/report_viewer.py",
    "services/receipt_printing.py",
    "receipt_printer.py",
    "history.py",
    "reports.py",
)
REQUIRED_JASPER_JARS = (
    "jasperreports-6.21.3.jar",
    "jasperreports-metadata-6.21.3.jar",
)


def validate_report_printing_gate(root: Path = ROOT) -> list[str]:
    """Return deterministic issues; an empty list means the gate passes."""
    issues: list[str] = []
    for rel in REQUIRED_FILES:
        if not (root / rel).is_file():
            issues.append(f"Missing reporting/printing file: {rel}")

    for module in REPORT_MODULES:
        try:
            __import__(module)
        except Exception as exc:
            issues.append(f"Reporting module import failed: {module}: {exc}")

    runtime = root / "jasper_runtime"
    for jar_name in REQUIRED_JASPER_JARS:
        jar = runtime / jar_name
        if not jar.is_file():
            issues.append(f"Missing Jasper runtime JAR: {jar_name}")
            continue
        try:
            with zipfile.ZipFile(jar) as zf:
                if zf.testzip() is not None:
                    issues.append(f"Corrupt Jasper runtime JAR: {jar_name}")
                if "META-INF/MANIFEST.MF" not in zf.namelist():
                    issues.append(f"Invalid Jasper runtime JAR signature: {jar_name}")
        except (zipfile.BadZipFile, OSError) as exc:
            issues.append(f"Unreadable Jasper runtime JAR: {jar_name}: {exc}")

    return sorted(set(issues))


def report_printing_gate_summary(root: Path = ROOT) -> dict[str, object]:
    issues = validate_report_printing_gate(root)
    return {
        "ok": not issues,
        "report_modules": list(REPORT_MODULES),
        "required_jasper_jars": list(REQUIRED_JASPER_JARS),
        "issues": issues,
    }
