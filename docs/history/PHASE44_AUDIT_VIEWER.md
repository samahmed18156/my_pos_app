# BKPOS Phase 44 — Audit History Viewer

Adds the query/report foundation for an authorized Audit / Activity History
screen.

## Filters
- Date range
- User
- Event type
- Document/reference type
- Document/reference number

## Rules
- Newest events first.
- Results are read-only.
- No delete/update API is exposed by this module.
- Results are capped to prevent an accidental unbounded query.

## Suggested UI
Management/Admin users can open Audit / Activity History, filter records,
inspect a selected event, and send the filtered result to JasperViewer for a
printable audit report.

The existing financial History screen remains separate: it is for document
lookup/reprint, while Audit History answers who/what/when questions.
