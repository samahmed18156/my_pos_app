from __future__ import annotations
from pathlib import Path
import subprocess, sys
from services.shop_smoke_gate import validate_shop_smoke_gate

ROOT = Path(__file__).resolve().parent
TESTS = [
    "tests/test_phase66_cashier_workflow.py",
    "tests/test_phase67_cashup_hardening.py",
    "tests/test_phase68_receipt_printing.py",
    "tests/test_phase69_document_numbering.py",
    "tests/test_phase70_day_end.py",
    "tests/test_phase76_upgrade_uninstall_safety.py",
]
issues = validate_shop_smoke_gate(ROOT)
print("BKPOS Phase 77 — Real-Shop Workflow Smoke Gate")
print("===============================================")
if issues:
    for issue in issues: print(f"FAIL: {issue}")
    raise SystemExit(1)
print(f"Critical workflow files: PASS")
print("Running critical in-memory/regression tests...")
result = subprocess.run([sys.executable, "-m", "pytest", "-q", *TESTS], cwd=ROOT)
if result.returncode:
    raise SystemExit(result.returncode)
print("PHASE 77 SHOP SMOKE: PASS")
