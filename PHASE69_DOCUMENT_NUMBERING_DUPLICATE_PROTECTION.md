# BKPOS Phase 69 — Document Numbering & Duplicate Transaction Protection

Phase 69 hardens transaction identity for production shop use.

## Stable document numbers
- Sales invoices now use `INV-000001`, `INV-000002`, ... from the database sequence.
- Customer returns / credit notes use `CN-000001`, `CN-000002`, ...
- GRNs continue using `GRN-000001`, ...
- Supplier stock credits use `SCN-000001`, ...
- Stock transfers continue using `TRF-000001`, ...
- Existing sales and returns are backfilled from their existing IDs so historical documents keep stable numbers.

## Duplicate transaction protection
Core transactional services accept an optional `transaction_uid`.
If a caller retries the same transaction with the same UID, BKPOS returns the original transaction instead of creating another document or changing stock a second time.

Protected transactions:
- Sales
- GRNs
- Customer returns
- Supplier stock credits

Database uniqueness is enforced with partial unique indexes so legacy rows with no UID remain valid.

## Database migration
Schema version is now 4. The migration is additive and idempotent. It does not delete or rewrite business transactions.

## Verification
- Phase 63–68 regression tests: PASS
- Phase 69 tests: PASS
- Combined targeted tests: 12/12 PASS
- Python compilation: PASS
- Phase 65 production audit: PASS
- Release package contains no `pos_store.db`, `.pyc`, or `__pycache__` artifacts.

The installed BKPOS executable is not modified by this development phase.
