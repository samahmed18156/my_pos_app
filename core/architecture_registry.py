"""BKPOS Phase 46 — architecture/security consolidation registry.

The core security modules are the preferred canonical implementations.
Legacy root-level modules are retained for compatibility until their live
imports are migrated and regression-tested.
"""

CANONICAL_SECURITY_MODULES = {
    "permissions": "core.permissions",
    "audit_log": "core.audit_log",
    "audit_viewer": "core.audit_viewer",
}

LEGACY_SECURITY_MODULES = {
    "permissions": "permissions.py",
    "audit_log": "audit_log.py",
    "security_controls": "security_controls.py",
}

def canonical_module(name: str):
    return CANONICAL_SECURITY_MODULES.get(name)
