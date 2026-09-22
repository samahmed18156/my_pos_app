# Phase 46 — Permissions Migration

`core.permissions` is the preferred canonical permission policy.

The legacy root `permissions.py` is intentionally retained in this phase
because automated reference analysis cannot prove that every external/runtime
caller has migrated. Existing behaviour is preserved.

Migration rule for future edits:
    from core.permissions import has_permission, require_permission

Do not delete the root module until its remaining references are migrated and
the full test suite passes.
