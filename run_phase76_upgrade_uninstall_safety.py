from pathlib import Path

from services.upgrade_uninstall_safety import upgrade_uninstall_safety_summary

ROOT = Path(__file__).resolve().parent
result = upgrade_uninstall_safety_summary(ROOT)
print("BKPOS Phase 76 — Upgrade & Uninstall Data Protection")
print("====================================================")
print(f"Identity: {result['app_name']} {result['app_version']}")
print(f"Installer data protection: {'PASS' if result['safe'] else 'FAIL'}")
for issue in result["issues"]:
    print(f"FAIL: {issue}")
if not result["safe"]:
    raise SystemExit(1)
print("User database preservation: PASS")
print("FINAL STATUS: PASS")
