# BKPOS Phase 70 — Day-End, Recovery, Operator Errors & Stability

Phase 70 adds the final real-shop operating procedure layer before final polish.

## Added
- `services/day_end_procedure.py`
  - database health gate
  - open-shift warning
  - cash-up variance warning
  - verified day-end SQLite backup
  - backup retention (20 newest backups)
  - optional SQLite planner optimization
  - read-only recovery guidance
- `services/operator_errors.py`
  - consistent operator-facing messages for printer, database, backup,
    duplicate transaction, permissions, shifts and cash-up variances
- Phase 70 tests for day-end checks, backup verification and operator messages.

## Safety rules
- A failed health check prevents normal day-end backup/optimization work.
- Backups are created through SQLite's online backup API and verified before
  being reported as successful.
- Day-end never overwrites or restores the live database.
- Recovery remains a deliberate, validated operation using the Phase 62/49
  recovery services.
- Existing BKPOS transactions and the installed executable are not modified.
