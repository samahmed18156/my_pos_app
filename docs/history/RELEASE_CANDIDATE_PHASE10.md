# BKPOS Phase 10 — Release Candidate Testing

This phase focuses on proving that the stabilized application can start cleanly,
load its core modules, create a fresh database, run its complete automated suite,
and report failures without requiring a printer, scanner, or other physical hardware.

## Run the checks

From the `phase10` project directory:

```text
python release_check.py
```

For only the automated tests:

```text
python run_tests.py
```

## Release-candidate checks

- Core module imports
- Fresh/first-launch database creation
- Required core tables
- SQLite integrity
- Complete automated test suite
- No physical hardware dependency for headless checks

## Manual checks still required before a real shop deployment

- Windows installer/package on a clean PC
- Login and role/permission walkthrough
- Actual barcode scanner
- Actual receipt printer/cash drawer
- JasperViewer/report rendering
- Backup and restore through the GUI
- Power-loss/crash simulation on the target machine
- Long-running day with real hardware
