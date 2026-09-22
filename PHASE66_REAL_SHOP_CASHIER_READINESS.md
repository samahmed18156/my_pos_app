# BKPOS Phase 66 — Real-Shop Cashier Readiness

Phase 66 strengthens the daily cashier workflow without changing the existing
sales, stock or accounting posting engines.

## Delivered

- `services/cashier_workflow.py` is the canonical shift/cash-drawer service.
- Cashier opening floats are validated and an already-open shift cannot be opened again.
- Cash drawer `PAY_IN` and `PAY_OUT` entries are recorded against the shift.
- Cash payouts require a reason.
- Shift expected cash reconciles existing cash sales, customer cash account
  payments, cash refunds, supplier cash payments, operating cash expenses and
  explicit drawer movements.
- Closing a shift records actual cash, expected cash and the variance.
- A linked `cashup_records.shift_id` is added when the table exists.
- The existing ShiftWindow now uses the Phase 66 service and exposes Cash In / Cash Out.
- No existing installed BKPOS executable is modified.

## Data safety

The new schema is additive. Existing tables and transaction records are not
dropped. The Phase 66 drawer ledger is only created when the shift workflow is
used or its schema helper is called.
