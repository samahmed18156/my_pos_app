# BKPOS Phase 27 — Real-World Failure Testing

## Purpose

Phase 27 verifies that deliberately injected failures during multi-step financial and inventory postings do not leave committed partial transactions when the application's transaction contract is used: begin, post, commit only on success, rollback on exception.

## Failure scenarios covered

- Multi-item sale fails on the second stock movement: sale header, first item, stock and movements roll back.
- Multi-item GRN fails on the second stock movement: GRN header/items, stock, product cost and supplier ledger roll back.
- Customer return fails while recording the return stock movement: return rows and stock changes roll back.
- Duplicate GRN number is rejected without partially receiving the new GRN's stock or ledger entry.

## Result

Full test suite: **114 tests passed**.

The failure-injection tests use temporary/in-memory SQLite databases and do not touch the production `pos_store.db`.

## Production transaction contract

The tested services intentionally do not commit their own database connection. The UI callers commit only after the service returns successfully and roll back when an exception occurs. This keeps multi-table postings atomic.
