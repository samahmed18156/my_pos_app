"""BKPOS Phase 45: centralized role/permission policy."""
ROLES=("admin","manager","cashier")
PERMISSIONS={
"sales":{"admin","manager","cashier"},
"invoice_reprint":{"admin","manager","cashier"},
"history":{"admin","manager","cashier"},
"grn":{"admin","manager"},
"stock_adjustment":{"admin","manager"},
"price_change":{"admin","manager"},
"debtor_payment":{"admin","manager","cashier"},
"creditor_payment":{"admin","manager"},
"backup_restore":{"admin"},
"user_management":{"admin"},
"audit_history":{"admin","manager"},
"system_settings":{"admin","manager"},
}
def normalize_role(role):
    r=(role or "").strip().lower()
    return r if r in ROLES else ""
def has_permission(role,permission):
    return normalize_role(role) in PERMISSIONS.get(permission,set())
def require_permission(role,permission):
    if not has_permission(role,permission):
        raise PermissionError(f"Role '{normalize_role(role) or 'unknown'}' is not permitted to perform '{permission}'.")
def allowed_permissions(role):
    r=normalize_role(role)
    return sorted(p for p,roles in PERMISSIONS.items() if r in roles)
