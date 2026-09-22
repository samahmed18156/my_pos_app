# BKPOS Phase 71 — UI Consistency & Final UX Polish

Phase 71 introduces a shared desktop-window presentation layer without changing business logic.

## Included
- `ui/window_polish.py` centralizes BKPOS window titles, background palette, ttk configuration and Escape-to-close behavior.
- Key operational windows now use the shared window polish layer.
- POS root retains its existing BKPOS title and geometry while receiving the shared theme configuration.
- Existing workflows, permissions, database behavior, JasperViewer behavior and printing behavior are unchanged.

## Safety
- No live database is bundled in the release.
- The installed BKPOS executable is not modified by this phase.
- Business transactions are not rewritten by the UI polish layer.
