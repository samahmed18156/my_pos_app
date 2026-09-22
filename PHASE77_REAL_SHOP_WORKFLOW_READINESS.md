# BKPOS Phase 77 — Real-Shop Workflow Readiness

Phase 77 hardens the final operator path before the Gold Release.

## Critical workflow

1. Open cashier shift and opening float.
2. Record cash-in/cash-out with reasons.
3. Receive stock through GRN and update weighted-average cost.
4. Complete cash/card/split/credit sales with stock deduction.
5. Protect retried transactions with transaction UIDs.
6. Process customer returns and restore stock at historical COGS.
7. Handle receipt-printer failure without duplicating a sale.
8. Close the shift with denomination/variance controls.
9. Create a verified day-end backup without replacing the live database.
10. Preserve user data through upgrade/uninstall.

The Phase 77 smoke gate is read-only against the release tree and runs the
critical regression tests in an isolated test environment. It never uses or
modifies the user's live BKPOS database.
