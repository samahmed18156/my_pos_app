# BKPOS Phase 12 — Supplier Accounting Integrity

This phase strengthens the supplier-side accounting lifecycle without replacing the existing database.

## Lifecycle

GRN -> Supplier Liability -> FIFO Supplier Payment -> Supplier Credit Note -> Reconciled Outstanding Balance

## Changes

- GRN headers now maintain `paid`, `outstanding`, and `status` fields, added safely to older databases.
- Supplier payments are allocated FIFO across open GRNs through `supplier_payment_allocations`.
- Supplier credit notes reduce the originating GRN's outstanding amount without changing the original document total.
- A fully paid GRN can receive a supplier credit without creating a negative invoice balance; the credit remains part of the supplier control balance.
- Supplier payment and credit posting remain transaction-safe: callers can commit/rollback the complete operation.
- Existing `account_transactions` remains the supplier control ledger, avoiding double counting.

## Verification

- Full automated suite: 87/87 passing.
- Python compilation: PASS.
- The new end-to-end supplier test covers two GRNs, FIFO payment allocation, partial payment, supplier credit, and final supplier balance.
