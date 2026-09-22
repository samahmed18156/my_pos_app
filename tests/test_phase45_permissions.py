from core.permissions import *
def test_matrix():
    assert has_permission("admin","backup_restore")
    assert has_permission("manager","grn")
    assert not has_permission("cashier","grn")
    assert not has_permission("manager","backup_restore")
    assert has_permission("cashier","sales")
    assert not has_permission("cashier","creditor_payment")
def test_guard():
    require_permission("admin","user_management")
    try: require_permission("cashier","user_management")
    except PermissionError: pass
    else: raise AssertionError("cashier must not manage users")
