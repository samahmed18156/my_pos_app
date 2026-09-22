"""BKPOS Phase 77 — real-shop workflow smoke gate.

Read-only release checks for the critical operator path.  The gate deliberately
checks source/test coverage rather than touching a live BKPOS database.
"""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRITICAL_FILES = (
    "services/cashier_workflow.py",
    "services/cashup_hardening.py",
    "services/sales_service.py",
    "services/grn_service.py",
    "services/returns_service.py",
    "services/receipt_printing.py",
    "services/day_end_procedure.py",
    "services/upgrade_uninstall_safety.py",
    "tests/test_phase66_cashier_workflow.py",
    "tests/test_phase67_cashup_hardening.py",
    "tests/test_phase68_receipt_printing.py",
    "tests/test_phase69_document_numbering.py",
    "tests/test_phase70_day_end.py",
    "tests/test_phase76_upgrade_uninstall_safety.py",
)
REQUIRED_TOKENS = {
    "services/sales_service.py": ("transaction_uid", "post_sale", "change_stock"),
    "services/grn_service.py": ("post_grn", "transaction_uid", "change_stock"),
    "services/returns_service.py": ("post_return", "transaction_uid", "change_stock"),
    "services/cashier_workflow.py": ("open_shift", "close_shift", "record_cash_movement"),
    "services/receipt_printing.py": ("safe_print_receipt", "printer_diagnostics"),
    "services/day_end_procedure.py": ("run_day_end", "create_verified_day_end_backup"),
}

def validate_shop_smoke_gate(root: Path = ROOT) -> list[str]:
    root = Path(root)
    issues: list[str] = []
    for rel in CRITICAL_FILES:
        if not (root / rel).is_file():
            issues.append(f"Missing critical shop-readiness file: {rel}")
    for rel, tokens in REQUIRED_TOKENS.items():
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for token in tokens:
            if token not in text:
                issues.append(f"Missing critical workflow marker '{token}' in {rel}")
    # The live database must never be part of a development/release smoke run.
    if (root / "pos_store.db").exists():
        issues.append("Smoke/release tree must not contain live pos_store.db")
    return sorted(set(issues))

def shop_smoke_summary(root: Path = ROOT) -> dict[str, object]:
    issues = validate_shop_smoke_gate(root)
    return {"phase": 77, "safe": not issues, "critical_files": len(CRITICAL_FILES), "issues": issues}
