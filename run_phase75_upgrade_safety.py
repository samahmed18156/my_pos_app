from pathlib import Path
from services.upgrade_safety import upgrade_safety_summary

ROOT = Path(__file__).resolve().parent
summary = upgrade_safety_summary(ROOT)
print("BKPOS Phase 75 — Upgrade Safety Gate")
print(f"Release identity: {summary['app_name']} {summary['app_version']}")
print(f"Release tree gate: {'PASS' if summary['tree_ok'] else 'FAIL'}")
for issue in summary["issues"]:
    print(f" - {issue}")
raise SystemExit(0 if summary["tree_ok"] else 1)
