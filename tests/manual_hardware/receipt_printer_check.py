"""Manual physical thermal-printer verification for BKPOS.

Run this on the Windows machine with the target receipt printer installed.
This script sends ONE test receipt and never retries automatically.
"""
from receipt_printer import get_installed_printers, get_printer_name, test_printer

printer = get_printer_name()
installed = get_installed_printers()

print(f"Configured receipt printer: {printer}")
print("Installed Windows printers:")
for name in installed:
    print(f"  - {name}")

if printer not in installed:
    print(f"\nFAIL: '{printer}' is not installed/available in Windows.")
    raise SystemExit(1)

print(f"\nSending ONE test receipt to '{printer}'...")
try:
    ok = test_printer(printer)
except Exception as exc:
    print(f"FAIL: {exc}")
    raise SystemExit(1)

if not ok:
    print("FAIL: Windows did not accept the print job.")
    raise SystemExit(1)

print("PASS: Windows accepted the test receipt.")
print("Check the physical printer for paper, alignment, and cutter operation.")
