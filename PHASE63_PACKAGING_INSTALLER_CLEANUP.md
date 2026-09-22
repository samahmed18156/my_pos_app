# Phase 63 — Packaging & Installer Cleanup

## Objective

Make the Windows packaging tree consistently BKPOS-branded, keep the installed
application isolated from the PyCharm development project, and prevent local
runtime artifacts from being shipped as part of a release source ZIP.

## Completed

- Replaced legacy MiPOS-named Windows installer/build definitions with BKPOS names.
- Standardized executable output to `BKPOS.exe`.
- Standardized installer output to `BKPOS_Setup_Windows10.exe`.
- Standardized install directory to `%LOCALAPPDATA%\BKPOS`.
- Kept writable application data in `%APPDATA%\BKPOS`.
- Preserved per-user installation (`PrivilegesRequired=lowest`).
- Added a dedicated BKPOS desktop-shortcut builder.
- Added a clean Windows 10/11 packaging path for current Python versions.
- Kept the Windows 7 path isolated as an explicitly legacy option.
- Removed development/runtime artifacts from the release source tree: database,
  generated files, logs, pytest caches and bytecode caches.
- Updated packaging documentation to explain source-vs-installed separation.
- Assigned a new BKPOS installer AppId so this packaging definition does not
  silently treat an older MiPOS installer as the same Windows product.

## Safety

This phase changes only the PyCharm/master release source tree and packaging
scripts. It does not modify or uninstall any already-installed BKPOS executable.
