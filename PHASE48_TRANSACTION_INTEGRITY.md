# BKPOS Phase 48 — Transaction Integrity & Financial Controls

Phase 48 hardens the transaction boundary without changing the working POS UI.

## What was added
- `services/transaction_guard.py`: atomic transaction context with nested SQLite SAVEPOINT support.
- `services/transaction_integrity.py`: read-only reconciliation assertions for sales, GRNs, customer invoices, supplier GRNs and stock movements.
- Audit logging now respects caller-owned transactions: business audit events roll back with failed work, while standalone audit events remain durable.
- Schema migrations no longer commit a transaction owned by an outer caller.
- Dedicated Phase 48 tests cover rollback, nested transactions, migration atomicity and financial/stock invariants.

## Transaction rule
Services should continue to avoid committing their own business transaction. UI/application code may use `transaction(conn)` when it owns the boundary. If a transaction already exists, the helper creates a SAVEPOINT instead of committing or rolling back unrelated outer work.

## Financial rule
Before committing a finalized document, its header, line items, account balances and stock movements must reconcile. The assertion helpers are deliberately read-only so they can be used by UI code, tests and future service hardening without changing accounting data.

## Compatibility
This phase is additive. Existing service APIs and the installed BKPOS executable are not changed by this project ZIP.
