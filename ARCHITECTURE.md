# BKPOS Architecture

The project now uses a compatibility-preserving layered UI layout.

## Entry point
- `app.py` — startup orchestration, feature installers, and backwards-compatible exports.

## UI
- `ui/pos.py` — main `FamilySupermarketPOS` window.
- `ui/windows.py` — reusable POS popup windows.
- `ui/admin_portal.py` — admin portal implementation.
- `ui/branches.py` — branch-management implementation.

## Compatibility
`admin_portal.py` and `branches.py` remain as import shims so existing code using the old module paths continues to work.

## Business logic
Existing `services/` and `core/` modules remain separate from the UI and were not removed or renamed.

## Refactoring rule
This pass moves code only; it does not intentionally remove features, workflows, public classes, or installer functions.

Phase 55: explicit SQLite database maintenance and query-planner optimization helpers.
