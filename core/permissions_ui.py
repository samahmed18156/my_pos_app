"""BKPOS Phase 45 UI permission helpers."""
from .permissions import has_permission
def action_enabled(role,permission): return has_permission(role,permission)
def filter_actions(role,actions):
    return {label:perm for label,perm in actions.items() if has_permission(role,perm)}
