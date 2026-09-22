# BKPOS Phase 59 — Production Logging Hardening

Phase 59 hardens application logging for packaged Windows deployment.

## Changes

- Packaged builds write logs under the current user's `%APPDATA%\\BKPOS\\logs` directory.
- Source-mode development logging remains project-local.
- File logging uses rotation (2 MB per file, 3 backups) to prevent unbounded growth.
- Logging gracefully falls back to `NullHandler` if the preferred location is unavailable.
- Added read-only logging diagnostics via `services/logging_hardening.py`.
- Added safe context logging with redaction of password/token/secret/API-key fields.
- Added regression tests for logging safety and diagnostics.

## Safety

Phase 59 does not modify the database schema or business data and does not change
transaction behavior. The installed BKPOS application is not touched by this
source release.
