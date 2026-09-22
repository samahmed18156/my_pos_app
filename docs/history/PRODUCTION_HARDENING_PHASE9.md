# BKPOS Phase 9 — Production Hardening

This phase hardens the application without changing the normal sales workflow.

## Included
- SQLite online-backup API instead of copying a live database file.
- Atomic backup creation with integrity verification.
- Verified restore with a pre-restore safety backup.
- Backup retention (new automatic backups keep the newest 30 database files).
- Reusable permission enforcement helper for future service-layer authorization.
- Automated crash/rollback, backup/restore, retention and permission tests.

## Operational rule
A database restore replaces the active database. Restart BKPOS after restoring so every open connection is recreated against the restored file.

## Hardware
Receipt printers, cash drawers and barcode scanners remain outside the automated suite. They should be covered by a separate manual hardware checklist.
