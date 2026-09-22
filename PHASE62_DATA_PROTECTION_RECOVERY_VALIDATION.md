# BKPOS Phase 62 — Data Protection & Recovery Validation

Phase 62 adds non-destructive backup/restore validation for production support.

## Included
- `services/recovery_validation.py`
  - `validate_backup_roundtrip()` creates a temporary SQLite backup and runs full BKPOS health validation.
  - `validate_restore_roundtrip()` restores a verified backup into a temporary destination and validates it.
- Corrupt backups are rejected before restore.
- Existing destinations are never overwritten by the safe validation path.
- Temporary validation files are removed automatically.

## Safety
These helpers never replace the live BKPOS database. They are intended for support diagnostics, deployment checks and automated regression tests.
