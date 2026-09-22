# BKPOS Phase 75 — Upgrade & Data Preservation Safety

Phase 75 adds a read-only release-boundary gate focused on safe application upgrades.

## Checks
- Both Windows installers remain per-user (`PrivilegesRequired=lowest`).
- The installed application remains under `%LOCALAPPDATA%\\BKPOS`.
- Installer scripts do not target or package the live `pos_store.db`.
- Release trees reject a live `pos_store.db`.
- Release ZIPs reject `pos_store.db` and unexpected database files.
- Installer AppId and BKPOS release version remain consistent.

## Safety
The gate does not open, migrate, replace, or delete the live BKPOS database and does not touch the installed executable.
