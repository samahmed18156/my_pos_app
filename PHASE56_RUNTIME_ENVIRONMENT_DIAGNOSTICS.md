# BKPOS Phase 56 — Runtime Environment Diagnostics

Phase 56 adds a non-invasive deployment/runtime diagnostics layer.

## Purpose

BKPOS can now inspect whether its runtime folders, database file, filesystem
capacity, and Java availability look healthy without modifying business data.

## Checks

- Data, backup, receipt, and generated-report directories are readable/writable.
- The configured database file exists and is readable/writable when present.
- Free disk space is reported with a configurable warning threshold.
- Java availability is reported because JasperViewer depends on Java.
- The result distinguishes OK, WARN, and ERROR states.
- Diagnostics explicitly identify themselves as read-only.

## Safety

The diagnostics never create probe files, modify the database, run migrations,
or change application configuration. A missing database on a fresh installation
is reported as a warning rather than an error because normal startup creates it.

## Testing

Phase 56 adds regression coverage for missing/existing database paths, disk-space
reporting, read-only behavior, and the aggregate diagnostic structure.
