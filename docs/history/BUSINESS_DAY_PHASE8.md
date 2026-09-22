# BKPOS Phase 8 — Full Business-Day Reconciliation

This phase adds a repeatable end-to-end business-day test and strengthens cash-up reconciliation.

## Covered scenario

- Branch-specific opening stock
- GRN into a branch
- Cash sale
- Card sale
- Customer credit sale
- Customer payment
- Customer cash refund/return
- Supplier stock credit
- Supplier cash payment
- Cash operating expense
- Financial summary
- Debtor balance
- Creditor balance
- Cash-up expected cash
- Branch isolation
- Negative-stock protection

## Cash-up rule

Expected drawer cash is now:

`opening float + cash sales - cash refunds - cash supplier payments - cash operating expenses`

Card sales and credit sales do not enter the cash drawer. Voided sales are excluded.

## Verification

- 70 automated tests pass.
- Python compilation passes.
- SQLite integrity check passes.

This is still a development/stabilization build, not a production release.
