# BKPOS Phase 31 — Release Candidate & Final Acceptance

Phase 31 freezes the feature set and validates the application as a deployable POS release candidate.

## Acceptance scope

- Fresh database creation and repeatable initialization.
- Existing database preservation when initialization runs again.
- SQLite integrity and foreign-key checks.
- Verified backup creation using SQLite's backup API.
- Verified restore with a safety backup of the current database.
- Corrupt backup rejection; no silent replacement of a database.
- Backup retention/pruning.
- Core application module/import checks.
- Existing automated business, accounting, costing, security and rollback tests.
- Jasper runtime/report assets remain present in the release tree.

## Release rule

A release candidate must pass the full automated suite and the Phase 31 acceptance tests. A corrupt database must never be silently replaced by a new empty database. Recovery must be performed from a verified backup.

SQLite's `PRAGMA integrity_check` is used because SQLite documents it as a low-level consistency check covering malformed records, missing/surplus index entries and constraint errors; foreign-key violations are checked separately with `PRAGMA foreign_key_check`.

## Manual acceptance still required before a production deployment

- Clean Windows-machine installation/startup.
- Real printer/payment hardware check.
- Visual inspection of every JasperViewer report and printed invoice/GRN.
- A real shop's backup/restore rehearsal using a copied database, never the only live database.
- Final operator sign-off.
