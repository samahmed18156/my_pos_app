# BKPOS Phase 80 — Gold Release

Phase 80 promotes BKPOS from the 10.0.0 release candidate to the **10.0.0 Gold Release**.

## Final identity
- Application: BKPOS
- Application version: 10.0.0
- Windows executable version: 10.0.0.0
- Installer AppId remains stable for upgrades/uninstall
- Installation remains per-user (`PrivilegesRequired=lowest`)

## Release safety
- The live installed BKPOS executable is not modified by this release build.
- The live `%APPDATA%\\BKPOS\\pos_store.db` database is not opened, migrated, replaced, or packaged.
- Release artifacts exclude databases, bytecode, caches, logs, backups, build/output folders, and generated runtime data.

## Final gates
- Phase 66–79 regression set: PASS
- Phase 80 Gold Release tests: PASS
- Python compilation: PASS
- Phase 65 production audit: PASS
- Gold Release gate: PASS
- ZIP integrity gate: PASS

Phase 80 is the **Gold / production release baseline**. Further numbered phases should only be created for real defects, required business changes, or post-release enhancements.
