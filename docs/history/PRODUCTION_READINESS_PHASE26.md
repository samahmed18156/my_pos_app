# BKPOS Phase 26 — Production Readiness Audit

## Completed

Phase 26 adds a read-only production health audit in `services/production_readiness.py`.

### Database checks
- SQLite integrity check
- Required core tables
- Required columns for costing/history/reporting
- Negative global stock
- Negative branch stock
- Orphaned sale lines
- Orphaned GRN lines
- Stock movements pointing at missing products

### Jasper checks
- Bundled JasperReports 6.21.3 main JAR present and non-trivial
- JasperReports metadata JAR present and non-trivial

The diagnostics are read-only and do not modify the live database.

## Automated result

`120 passed, 15 subtests passed`

The test suite covers both the existing business workflows and the new production-readiness diagnostics.

## Operational rule

Run the readiness checks against a copy/backup of a production database before release. A clean report does not replace a normal backup and restore test.
