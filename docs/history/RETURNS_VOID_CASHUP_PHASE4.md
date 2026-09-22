# BKPOS Phase 4 — Returns, Voids & Cash-Up Integrity

This build strengthens the financial lifecycle without changing the existing UI design.

## Changes
- Returns are posted through `services/returns_service.py`.
- A return always restores stock to the branch where the original sale was posted.
- Return validation and stock/accounting changes are one transaction.
- Voids are posted through `services/financial_service.py`.
- Voids restore only quantities that were not already returned.
- Voids restore stock to the original sale branch.
- Void records include stock movements and transaction-control records.
- Cash-up calculations have a testable `cashup_summary()` service.
- Added automated tests for partial returns, over-returns, rollback, void protection, branch correctness and cash-up treatment.

## Verification
- 45 / 45 automated tests pass.
- Python compileall passes.
- SQLite integrity check: `ok`.

## Important rule
A return or void cannot redirect stock to the branch currently selected in the UI. Stock is restored to the branch recorded on the original sale.
