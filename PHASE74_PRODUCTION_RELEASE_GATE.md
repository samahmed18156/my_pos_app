# BKPOS Phase 74 — Production Release Gate

Phase 74 adds a deterministic final gate for release artifacts after the Phase 73 identity and upgrade-safety work.

## What it checks
- Required production/release files exist.
- BKPOS release identity remains consistent across version files, installers and PyInstaller specs.
- Live database files are excluded from the release tree.
- Python bytecode and development/build output are excluded.
- A built release ZIP can be checked without extracting or modifying it.
- Required metadata is present inside the ZIP.
- A release ZIP containing `pos_store.db`, caches, build output or bytecode is rejected.

## Safety
The gate is read-only. It does not open, modify, migrate, replace, or delete the live BKPOS database, and it does not touch the installed executable.
