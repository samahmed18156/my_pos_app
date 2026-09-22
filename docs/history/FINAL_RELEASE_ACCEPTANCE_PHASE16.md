# BKPOS Phase 16 — Final Release Acceptance

This phase is the final acceptance pack built from Phase 15.

## Automated checks
- Python compilation of every `.py` file
- Full unittest discovery
- Core module imports
- Fresh-database initialization tests
- Database integrity/preflight tests
- Backup/restore tests
- Permission/branch-isolation tests
- Sales, returns, voids, cash-up, debtor/creditor and purchasing regressions

## Real Windows acceptance checklist

Run these on the actual POS computer before deployment:

### 1. Clean launch
- Copy the project to a fresh folder.
- Start `app.py`.
- Confirm the login/main window opens without a traceback.

### 2. Existing-data launch
- Back up the production `pos_store.db`.
- Launch using the real database.
- Confirm existing products, branches, customers and suppliers are visible.

### 3. Admin
- Login as Admin.
- Verify management functions work.
- Verify cross-branch management works where intended.
- Create/restore a verified database backup.

### 4. Manager
- Login as Manager.
- Verify explicitly granted permissions work.
- Attempt a forbidden operation and confirm it is rejected.

### 5. Cashier
- Login as Cashier.
- Complete a normal cash/card sale.
- Attempt void, credit-note and management operations.
- Confirm unauthorized operations are rejected.

### 6. Hardware
- Barcode scanner
- Receipt printer
- Cash drawer
- JasperViewer/receipt preview

### 7. Recovery
- Start a test transaction.
- Close/restart the application.
- Restore a test backup.
- Confirm the database passes integrity check afterward.

## Release blocker
Any data loss, cross-branch access, unauthorized financial operation, corrupted database, or unrecoverable application crash blocks release.
