# Phase 19 — Performance & Scalability

Adds a management diagnostics center for database size, row/index counts, recommended index coverage and SQLite query-plan inspection.

The optimizer creates only missing, additive indexes on tables that exist. It never deletes or rewrites business records. The module is safe to use on databases with optional/legacy schemas because unavailable tables are skipped.

## Verification
- Performance diagnostics and optimizer tests
- Index optimizer idempotency
- Row-count preservation
- Query-plan and CSV export checks
- Full regression suite
