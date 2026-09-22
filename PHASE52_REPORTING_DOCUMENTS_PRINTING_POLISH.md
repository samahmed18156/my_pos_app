# Phase 52 — Reporting, Documents & Printing Polish

## Included
- Shared ISO date-period validation for report screens.
- Reports reject an inverted date range with a clear user-facing message.
- Descriptive BKPOS PDF filenames containing report type and period.
- Shared empty-report messaging helper for future report screens.
- Regression tests for report date and document-formatting behavior.
- Existing JasperViewer, PDF export and Windows printing paths preserved.

## Safety
This phase does not change financial calculations, database records, stock logic,
or transaction behavior. The working installed BKPOS is not modified.
