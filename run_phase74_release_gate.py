from __future__ import annotations

from pathlib import Path
import sys

from services.release_gate import release_gate_summary

ROOT = Path(__file__).resolve().parent
zip_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
result = release_gate_summary(zip_path)
print("BKPOS Phase 74 — Production Release Gate")
print("========================================")
print(f"Identity: {result['app_name']} {result['app_version']}")
print(f"Executable version: {result['exe_version']}")
print(f"Installer AppId: {result['installer_app_id']}")
print(f"Release tree: {'PASS' if result['tree_ok'] else 'FAIL'}")
if zip_path:
    print(f"Release ZIP: {'PASS' if result['zip_ok'] else 'FAIL'}")
if result["issues"]:
    for issue in result["issues"]:
        print(f"FAIL: {issue}")
    raise SystemExit(1)
print("FINAL STATUS: PASS")
