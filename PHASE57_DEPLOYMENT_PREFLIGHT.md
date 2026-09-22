# BKPOS Phase 57 — Deployment Preflight

Phase 57 adds a read-only production deployment preflight that combines the
runtime environment diagnostics from Phase 56 with the established BKPOS
database health checks.

## Features
- Single go/no-go report for operators and support staff.
- Runtime diagnostics, schema-version inspection, and database health.
- Distinguishes `OK`, `WARN`, and `ERROR` without changing application data.
- Missing database is a warning because a first launch may legitimately create it.
- Corrupt/unreadable databases fail preflight.
- Reports packaged/source mode, Python version, app version, and database path.

## Safety
The preflight is strictly read-only. It does not run migrations, ANALYZE,
VACUUM, PRAGMA optimize, repairs, backups, or database writes.
