# BKPOS Phase 7 — Purchase Lifecycle Integrity

This phase closes the purchasing-side accounting loop:

**GRN → branch stock → global stock → supplier liability → supplier credit note → supplier payment**

## Changes

- Added `services/grn_service.py` as the transactional GRN business layer.
- Added `services/supplier_credit_service.py` as the transactional supplier stock-return layer.
- GRN posting now links the supplier by `supplier_id`, receives stock in the selected branch, updates global stock, records a stock movement, and creates one supplier purchase ledger entry in the same transaction.
- Supplier stock credits are tied to exact GRN items and cannot exceed the remaining received quantity.
- Supplier stock credits cannot create negative branch stock or exceed the supplier liability.
- Supplier balances prefer authoritative GRNs plus supplier payments and credits, with legacy fallback support.
- `accounts_service.supplier_payment()` now uses GRNs for outstanding-liability validation when available.
- Stock-movement recording supports both the current barcode/quantity schema and the older product_id/quantity schema found in legacy databases.
- Existing UI workflows now call the transactional GRN and supplier-credit services.

## Tests

The automated suite now contains **68 tests** and all pass.

The new purchase lifecycle tests cover:

- GRN posting and VAT calculation
- Branch-specific receiving
- Global stock consistency
- Product cost update
- GRN rollback on invalid item
- Exact GRN-item supplier credits
- Partial supplier credits
- Over-credit prevention
- Negative-stock prevention
- Supplier payment reconciliation
- Supplier overpayment prevention

## Validation

- `python run_tests.py` → **68/68 PASS**
- `python -m compileall -q .` → PASS
- SQLite `PRAGMA integrity_check` → **ok**
