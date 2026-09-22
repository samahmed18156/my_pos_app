# Phase 55 — Database Maintenance & Query Planner Optimization

Phase 55 complements the Phase 54 index work by adding explicit, safe SQLite
maintenance operations. It does not change the business schema or transaction
logic.

## Included
- `services.database_maintenance.maintenance_report()` — read-only page/free-space diagnostics.
- `analyze_database()` — refreshes SQLite query-planner statistics after major data/index changes.
- `optimize_database()` — invokes SQLite's `PRAGMA optimize` for opportunistic optimizer maintenance.
- `vacuum_database()` — explicit database compaction with a safety guard that refuses to run during an active transaction.
- Automated tests covering read-only diagnostics, ANALYZE, optimizer maintenance and VACUUM transaction safety.

## Safety
- No business rows are deleted or rewritten by the maintenance service.
- VACUUM is never attempted while a transaction is active.
- No schema version bump is required; Phase 54 remains schema version 3.
- Maintenance is explicit rather than silently running during every POS transaction.

## Operational guidance
After a large import, historical cleanup, or index migration, run `ANALYZE`
and/or `PRAGMA optimize`. Use `VACUUM` only during a quiet maintenance window
because it rebuilds the SQLite database file.

## Relationship to Phase 54
Phase 54 adds targeted indexes. Phase 55 makes sure SQLite's query planner has
fresh statistics and provides controlled file-space maintenance so the indexes
can remain useful as the database grows.
