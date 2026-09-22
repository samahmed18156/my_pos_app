# Phase 68 — Receipt Printing & Printer Failure Handling

## Production goals
- Keep completed sales safe when a receipt printer is unavailable.
- Never automatically retry a receipt print, preventing accidental duplicate receipts.
- Give the cashier an actionable printer error and direct them to History for reprint.
- Allow the receipt printer name to be configured with `BKPOS_RECEIPT_PRINTER` without editing source code.
- Provide read-only printer diagnostics for support and deployment checks.

## Operator behaviour
A printer failure does **not** roll back a completed sale. The transaction remains posted and can be reprinted from History after the printer problem is corrected.

## Hardware testing
Physical printer testing remains a manual step because it requires the target Windows printer hardware. The included test suite uses mocked Windows printing APIs and does not claim physical printing success.
