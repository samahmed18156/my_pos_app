# BKPOS Phase 67 — Opening, Closing & Cash-Up Hardening

Phase 67 hardens the Phase 66 cashier workflow for real daily operation.

## Delivered
- Database-level partial unique index prevents two OPEN shifts for the same cashier.
- Cash-up validates physical denomination counts when supplied.
- Denomination totals must equal the declared physical cash amount.
- Any non-zero cash variance requires an operator reason.
- Cash-up records preserve denomination snapshot, count time, variance reason and optional approver metadata.
- Shift close uses an atomic status guard and refuses stale/concurrent closes.
- Failed cash-up validation leaves the shift OPEN.
- Existing sales, stock, debtor/creditor and accounting posting engines are unchanged.
