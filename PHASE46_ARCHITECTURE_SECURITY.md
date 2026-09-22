# BKPOS Phase 46 — Architecture & Security Consolidation

## Objective
Consolidate security/audit architecture without breaking the working POS.

## Canonical direction
- `core.permissions` — canonical role/permission policy
- `core.audit_log` — canonical audit storage/event API
- `core.audit_viewer` — canonical audit querying/viewer foundation

## Safety rule
Legacy root-level modules are NOT deleted automatically. They are retained
until all live imports are migrated and the complete test suite proves the
application still works.

## Database rule
No runtime `pos_store.db` is shipped with the development project archive.
Existing user databases must be upgraded by application migrations, never
replaced by a bundled blank database.

## Phase 46 changes
- Added an architecture registry.
- Documented canonical security modules.
- Added migration guidance.
- Preserved legacy modules to avoid breaking unknown callers.
- Added automated inventory/reporting of duplicate security modules.

This phase is intentionally conservative: it improves architecture without
changing accounting calculations or transaction workflows.
