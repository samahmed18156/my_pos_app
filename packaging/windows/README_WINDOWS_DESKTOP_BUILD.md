# BKPOS Windows Desktop Build

## Windows 10/11

Run `MAKE_BKPOS_INSTALLER.bat` and choose option 1.

The modern build accepts Python 3.13 and creates `dist\BKPOS\BKPOS.exe`.
Inno Setup 6 creates a per-user installer named `BKPOS_Setup_Windows10.exe`.

## Installation

The installer uses `PrivilegesRequired=lowest` and installs to the current
user's LocalAppData:

`%LOCALAPPDATA%\BKPOS`

BKPOS writable application data is kept separately under the user's AppData
area (`%APPDATA%\BKPOS`). This keeps the installed application and its live
data separate from the PyCharm source project.

## Legacy Windows 7

Option 2 remains isolated in `build_bkpos_legacy.bat` and requires Python 3.8
32-bit plus a supplied Java 8 runtime. It is retained only for legacy builds.

## Important packaging rule

Do not include `pos_store.db`, `__pycache__`, `.pyc`, `logs`, or generated test
output in a release ZIP. The installer is built from the clean `dist\BKPOS`
tree, not from the development database.

## Phase 64 configuration policy

BKPOS deployment paths are centralized in `core/deployment_config.py`.
The installed executable directory and writable user-data directory are kept
separate. Source-mode development continues to use the project-local database.
Do not hard-code alternate database locations into application modules.

## Phase 72 installer policy

- Installer identity is BKPOS 10.0.0.
- Desktop shortcut creation is optional and unchecked by default.
- Start Menu entries are retained for BKPOS, BKPOS Data Folder, and Uninstall BKPOS.
- BKPOS remains a per-user installation (`PrivilegesRequired=lowest`).
- The executable carries BKPOS Windows file/product version metadata.
- Installer packages must never contain the live `pos_store.db`; installed data belongs under `%APPDATA%\BKPOS`.
