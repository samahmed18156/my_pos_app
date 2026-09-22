# BKPOS Phase 15 — Final Release Hardening

This phase is the final software-side hardening pass.

## Added
- Database preflight validation before release/use.
- Verified timestamped release backups using SQLite online backup.
- Backup retention remains enforced.
- Automated checks for missing/corrupt databases.
- Release hardening tests.

## Verified
The complete automated suite must pass before a release ZIP is produced.

## Still requires physical Windows acceptance
- Install/copy to a clean Windows machine.
- Login as Admin, Manager, Cashier and test allowed/forbidden actions.
- Receipt printer and cash drawer.
- Barcode scanner.
- JasperViewer installation/runtime.
- Backup/restore using the user's real database.
- Simulated unexpected application termination.

Do not call the product production-ready until those manual checks pass.
