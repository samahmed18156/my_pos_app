# BKPOS Phase 17 — Operational Deployment Runbook

## Before first deployment
1. Make a copy of the current `pos_store.db`.
2. Keep that backup outside the application folder.
3. Copy the Phase 17 application files over the application folder.
4. Do not replace the database with a clean/test database.
5. Run `MIPOS_PRE_DEPLOY_CHECK.bat`.

## First launch
Use `START_MIPOS.bat` or run `python app.py`.
Confirm:
- login opens
- existing products/branches/customers/suppliers remain present
- no migration traceback appears

## Daily opening
- Confirm correct branch.
- Confirm opening cash/float.
- Confirm printer/scanner are available.
- Make a small test transaction if the shop's operating procedure allows it.

## Daily closing
- Finish all sales.
- Process legitimate returns/credits.
- Complete cash-up.
- Verify cash/card/credit totals.
- Create a verified database backup before maintenance or major upgrades.

## Upgrade rule
Never overwrite `pos_store.db` with a database from a ZIP.
Back up first, then replace application files only.

## If something breaks
1. Stop transactions.
2. Preserve the traceback/error message.
3. Do not delete or recreate the database.
4. Keep the latest verified backup.
5. Send the complete traceback for diagnosis.

## Hardware acceptance
On the real Windows POS machine verify:
- barcode scanner
- receipt printer
- cash drawer
- JasperViewer/receipt preview

## Release rule
Any data loss, cross-branch access, unauthorized financial action, database corruption, or unrecoverable crash is a release blocker.
