# BKPOS Phase 37 — Final Business Controls

Phase 37 strengthens the production baseline without changing the working accounting engine.

## Added
- Schema-aware date-column validation for History sources.
- Regression guard against `customer_account_payments.created_at`.
- Canonical production pre-deployment checker.
- Business-control validation integrated into `release_check.py`.
- Release archive excludes the live `pos_store.db` and generated Jasper output.

## Operator acceptance already completed
- Products
- GRN/purchasing
- Cash and credit sales
- Debtor payment
- Debtor/creditor accounts
- History
- JasperViewer reprinting
- Reports

Printer hardware remains a later physical acceptance test.
