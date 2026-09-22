# BKPOS Phase 6 — Debtor & Creditor Integrity

This phase adds a testable accounting service for customer and supplier account transactions.

## Covered workflows
- Credit sale -> customer debtor balance
- Customer payment -> oldest invoice first allocation
- Partial customer payment
- Credit-sale return -> original invoice outstanding reduced
- Customer payment over outstanding balance rejected
- Supplier purchase -> supplier liability
- Supplier payment -> supplier liability reduced
- Supplier credit -> supplier liability reduced
- Supplier overpayment rejected unless an explicit advance is allowed
- Supplier advance balance is represented as a negative outstanding balance
- Supplier balance reconciliation includes supplier credits

## Test command
`python -m unittest discover -s tests -v`

## Result for this build
59/59 tests pass.
