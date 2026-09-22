# BKPOS Phase 11 — Release Candidate Validation

## Automated validation completed

- Full automated suite: PASS
- Core imports: PASS
- Fresh first-launch database: PASS
- Repeat initialization: PASS
- SQLite integrity check: PASS
- Python compilation: PASS
- ReportLab availability: PASS
- Tkinter import: PASS
- Jasper receipt bridge import: PASS
- Jasper JRPXML generation: PASS
- JasperViewer missing-runtime handling: PASS
- Printer integration is safe in headless/non-Windows environments: PASS

## Manual machine checks still required

These cannot be honestly certified inside the development container because they require the user's Windows machine and physical devices/runtime:

1. Launch `app.py` by double-clicking on Windows.
2. Log in as admin and create a test cashier.
3. Verify cashier permissions and branch assignment.
4. Scan a real barcode with the USB scanner.
5. Complete a cash sale and verify the physical receipt.
6. Complete a card sale.
7. Test split payment.
8. Test customer credit sale and payment.
9. Open JasperViewer with the installed Jasper runtime.
10. Print to the actual Epson thermal printer.
11. Test cash drawer opening if connected.
12. Create a verified backup, close POS, restore to a test copy, and reopen.
13. Restart Windows and verify the POS/database remain usable.

Do not treat these as failed tests: they are hardware/Windows acceptance tests that require the real shop environment.
