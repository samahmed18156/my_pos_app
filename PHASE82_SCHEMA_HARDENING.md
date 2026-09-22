# BKPOS Phase 82 — Database Schema & Transaction Hardening

## Purpose
Fix schema mismatches found while testing the BKPOS 10.0.0 development build, especially the sale-confirmation failure:

`table audit_log has no column named role`

## Fixes included
- Audit-log compatibility columns are now migrated safely (`role`, `action`, `entity_type`, `entity_id`, `details`, `branch_id`, `timestamp`, `reference`).
- Database audit triggers now write the canonical `event_time` and `event_type` fields as well as legacy reporting fields.
- Legacy audit writers now supply the required canonical audit fields.
- `sales_history` startup schema now guarantees payment, customer, status, document-number and transaction-UID columns.
- `sale_items.cost_price` is guaranteed before sale posting, preventing the next schema failure after the audit issue.
- Supplier credit tables now guarantee `transaction_uid` and its unique index.
- Fresh databases receive the complete current sales schema rather than relying on later screen-specific migrations.
- Removed a duplicate `return_history.total_amount` declaration found during review.
- Release-quality duplicate detection is deterministic.
- Cleaned pass-only exception handlers flagged by maintainability checks.
- Phase 54 tests were aligned with the current schema-manager version 4.

## Safety
The production/installed BKPOS database is not included in this development ZIP. The ZIP contains source code only. Existing user databases are upgraded additively; no tables or business records are dropped by these changes.

## Validation
- Sale posting tested against a fresh database with audit triggers enabled: PASS.
- Sale posting tested against the uploaded existing development database copied to a test database: PASS.
- Targeted sales, supplier lifecycle, audit and document-number tests: **26 passed**.
- Additional release-quality, migration and maintainability tests: **10 passed**.
