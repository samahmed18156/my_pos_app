# Phase 64 — Configuration & Deployment Cleanup

## Objective

Centralize BKPOS deployment identity and filesystem policy so development,
installed application files, and writable user data remain clearly separated.

## Completed

- Added `core/deployment_config.py` as the single source of truth for:
  - application name/version
  - packaged vs source mode
  - application base directory
  - writable data directory
  - database, backup, receipts and generated-report directories
  - logs, diagnostics and runtime directories
- Updated `core/config.py` to consume the centralized deployment policy while
  preserving existing database backup and MiPOS-to-BKPOS migration behavior.
- Added non-mutating configuration/deployment health checks in
  `services/configuration_health.py`.
- Added Phase 64 regression tests covering source-mode paths, packaged-mode
  separation, safe deployment summaries and configuration health.
- Kept all runtime directories out of the release source package.
- No live installed BKPOS executable or user database is modified by this phase.

## Deployment policy

### PyCharm/source mode

The development database remains project-local for compatibility and testing.

### Packaged Windows mode

The application is installed under `%LOCALAPPDATA%\BKPOS` while writable
application data is stored under `%APPDATA%\BKPOS`.

This prevents the installed executable from sharing the development database
and avoids requiring Administrator rights for normal data operations.
