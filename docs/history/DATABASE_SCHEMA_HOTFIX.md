# Database Schema Hotfix

## Problem fixed
Some older BKPOS databases contain the legacy `stock_movements` columns:
`product_id`, `quantity`, and `created_at`. The release candidate startup code
previously tried to create an index on the newer `barcode` and `timestamp`
columns before migrating the old table, causing:

`sqlite3.OperationalError: no such column: barcode`

## Fix
`database.py` now upgrades an existing legacy `stock_movements` table in-place,
adds the canonical columns, preserves existing rows, backfills barcode,
description, quantity and timestamp where possible, and only then creates the
index.

`production_upgrade.py` also skips that index if an external/older database
still lacks the required columns.

## Safe installation
Copy/merge the contents of this hotfix over your existing BKPOS project.
**Do not delete or replace your existing `pos_store.db` unless you have a backup.**
The normal startup migration is designed to upgrade it in place.
