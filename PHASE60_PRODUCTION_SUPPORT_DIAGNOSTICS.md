# BKPOS Phase 60 — Production Support Diagnostics

Phase 60 adds a safe troubleshooting report for packaged BKPOS installations.

## Included

- Collects app, Python, Windows/platform and packaged-build information.
- Includes runtime diagnostics, database health and logging status.
- Writes a small text report to `%APPDATA%\\BKPOS\\diagnostics` in packaged mode.
- Does not copy the live database into the report.
- Does not include passwords, tokens, API keys or other obvious secrets.
- Keeps diagnostics outside the application/program directory.

## Safety

The feature is read-only with respect to business data. Generating a report does
not alter the SQLite database, perform migrations, or modify installed files.
