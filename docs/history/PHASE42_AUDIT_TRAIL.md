# BKPOS Phase 42 — Audit Trail

## Purpose
Provide a central audit trail for important business and security events.

## Added
- `core/audit_log.py`
- `audit_log` SQLite table created on demand
- Timestamp, username, event type, description and document reference fields
- Optional structured details stored as JSON
- Recent-event retrieval helper

## Safety
This phase intentionally does not rewrite existing sales, stock, debtor,
creditor, payment, or reporting workflows. It provides a controlled service
that can be integrated into those workflows after individual tests.

## Recommended events
- Login success/failure
- Logout
- Sale created/voided
- Invoice/credit note created
- GRN created/edited
- Debtor/creditor payment posted
- Document reprinted
- Product/price changes
- Backup/restore
- Settings/security changes

Never store passwords or payment-card data in the audit log.
