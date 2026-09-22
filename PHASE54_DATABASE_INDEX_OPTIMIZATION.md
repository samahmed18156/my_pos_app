# Phase 54 — Database Index Optimization

Phase 54 turns the measurement foundation from Phase 53 into a safe,
repeatable database optimization step.

## Included
- Additive schema migration 3 for targeted SQLite indexes.
- Indexes cover frequent product, sales, GRN, stock, branch, debtor/creditor,
  audit, shift, cash-up, returns, alerts and loyalty lookups.
- Missing optional tables/columns are ignored safely.
- Migration is idempotent and never drops business data or existing indexes.
- Read-only `services.index_optimization.index_health()` reports whether the
  Phase 54 indexes are present.
- Automated regression tests for creation, idempotency and optional tables.

## Safety
The migration uses `CREATE INDEX IF NOT EXISTS` and checks table/column
existence first. Existing databases are upgraded through `PRAGMA user_version`
from schema version 2 to 3. A database newer than BKPOS remains protected from
accidental downgrade.

## Relationship to Phase 53
Phase 53 supplied query-plan and benchmark tools. Phase 54 applies only the
low-risk indexes justified by the application's existing high-frequency lookup
patterns, while keeping business calculations and transaction behavior
unchanged.
