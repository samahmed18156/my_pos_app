# BKPOS Phase 43 — Business Activity Audit

Defines a consistent audit vocabulary for completed business actions.

Event types:
- SALE_CREATED
- INVOICE_CREATED
- CREDIT_NOTE_CREATED
- DEBTOR_PAYMENT_RECEIVED
- CREDITOR_PAYMENT_MADE
- GRN_CREATED
- STOCK_ADJUSTMENT
- RETURN_PROCESSED
- DOCUMENT_REPRINTED
- PRODUCT_CHANGED
- PRICE_CHANGED
- BACKUP_CREATED
- BACKUP_RESTORED
- LOGOUT

Business events should be recorded only after the underlying transaction has
successfully committed. Never store passwords, card data, or secrets.

The central `record_business_event()` helper is intentionally small so existing
financial workflows can be integrated one at a time and tested safely.
