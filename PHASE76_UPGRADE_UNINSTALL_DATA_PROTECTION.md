# BKPOS Phase 76 — Upgrade & Uninstall Data Protection

Phase 76 hardens the Windows installer boundary so application upgrades and
uninstalls cannot accidentally remove or package the live BKPOS user database.

## Protection rules
- The BKPOS application remains installed under `%LOCALAPPDATA%\\BKPOS`.
- User data remains under `%APPDATA%\\BKPOS`.
- Both installers remain per-user (`PrivilegesRequired=lowest`).
- The stable BKPOS installer AppId is preserved for upgrades.
- The release version remains `10.0.0-rc1`.
- No `[UninstallDelete]` section is permitted for BKPOS user data.
- `pos_store.db` must never appear in installer sources or destinations.
- The Start Menu **BKPOS Data Folder** shortcut may reference the user-data folder;
  that reference does not package or delete the data.

## Safety
The Phase 76 gate is read-only. It does not open, migrate, replace, delete, or
repair the live database and does not modify the installed BKPOS executable.
