# BKPOS Phase 49 — Database & Recovery Hardening

Phase 49 adds read-only database diagnostics and safe recovery primitives.

## Health checks
- SQLite `quick_check`
- foreign-key violations
- required tables and columns
- orphan sale/GRN/stock rows
- negative stock diagnostics
- clear problem details in POS Health Check

## Recovery
- verify backup health before restore
- restore through a temporary SQLite backup file
- validate the restored file before activation
- refuse to overwrite an existing destination

The active installed BKPOS database is never modified by these diagnostics.
