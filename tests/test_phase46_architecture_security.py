from core.permissions import has_permission, require_permission
from core.architecture_registry import canonical_module, CANONICAL_SECURITY_MODULES

def test_canonical_security_modules():
    assert canonical_module("permissions") == "core.permissions"
    assert canonical_module("audit_log") == "core.audit_log"
    assert canonical_module("audit_viewer") == "core.audit_viewer"

def test_canonical_permissions_still_work():
    assert has_permission("admin", "user_management")
    assert not has_permission("cashier", "user_management")
    require_permission("manager", "grn")
