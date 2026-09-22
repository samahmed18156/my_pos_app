# BKPOS Stabilization Pass

This build is the stabilized baseline after the Phase 1 review.

## Changes made

- Added standard-library PBKDF2-SHA256 password hashing.
- Existing plaintext passwords are migrated once at database initialization and blanked.
- New users and password resets store only password hashes.
- Fixed the stock service to use the actual `stock_movements` schema (`barcode`, `qty`, `qty_before`, `qty_after`, etc.).
- Stock movement recording can now participate in the caller's transaction.
- POS sales now validate product existence and available stock before reducing SOH.
- POS sales fail/rollback if the stock movement cannot be recorded; stock history can no longer silently drift from SOH during a sale.
- Database startup no longer drops the entire `products` table when an older schema is detected.
- Historical `app_before_*` and `app_old.py` snapshots were moved into `archive/legacy_app_versions/` so there is one active `app.py`.
- The receipt-printer check was moved to `tests/manual_hardware/` so automated test discovery does not depend on a physical printer.
- Added automated security and stock-service tests.
- Modules using `DB_NAME` now resolve the database through `core.config.DB_PATH` where applicable.

## Remaining deliberate boundary

The multi-branch UI remains a separate branch-stock subsystem. The current POS screen still uses the main `products.soh` field rather than silently switching to branch-specific stock. This is intentional: making branch stock canonical requires changing product lookup, sale posting, GRN, returns, transfers, reports and cash-up together. It should be implemented as a dedicated branch-integration phase rather than a risky partial patch.
