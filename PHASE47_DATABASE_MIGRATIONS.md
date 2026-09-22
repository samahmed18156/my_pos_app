# BKPOS Phase 47 — Database Migration Hardening

## Goal
Make future SQLite schema upgrades explicit, repeatable and safe.

### New canonical migration manager
`core.schema_manager`

It uses SQLite `PRAGMA user_version` and two additive migrations:
1. Audit-log compatibility schema.
2. Stock-movement compatibility schema.

### Safety rules
- No DROP TABLE.
- No deletion of business rows.
- No replacement of the live database.
- Migrations are idempotent.
- A database newer than the application is rejected rather than downgraded.
- Legacy columns are preserved.

The existing `database.init_db()` compatibility logic remains in place in this
phase. The new manager is a controlled foundation for gradually consolidating
future schema work. Existing startup behaviour is therefore not replaced
blindly.
