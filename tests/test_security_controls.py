import sqlite3
import pytest
from security_controls import ensure_permission_schema, has_permission, require_permission, require_branch


def test_permission_schema_adds_security_columns(tmp_path, monkeypatch):
    db=tmp_path/'p.db'; c=sqlite3.connect(db)
    c.execute('CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT, role TEXT)'); c.commit()
    ensure_permission_schema(c)
    cols={r[1] for r in c.execute('PRAGMA table_info(users)')}; c.close()
    assert {'can_void_sales','can_issue_credit_notes','can_manage_users','can_manage_branches','can_cashup','can_manage_expenses'} <= cols


def test_admin_bypasses_permission():
    actor={'username':'admin','role':'Admin'}
    assert has_permission(actor,'can_void_sales')
    require_permission(actor,'can_void_sales')


def test_cashier_cannot_void():
    actor={'username':'c','role':'cashier','can_void_sales':False}
    with pytest.raises(PermissionError): require_permission(actor,'can_void_sales')


def test_authorized_manager_can_void():
    actor={'username':'m','role':'manager','can_void_sales':True}
    require_permission(actor,'can_void_sales')


def test_branch_isolation():
    actor={'username':'b','role':'cashier','branch_id':2}
    assert require_branch(actor,2)==2
    with pytest.raises(PermissionError): require_branch(actor,1)


def test_admin_can_operate_other_branch():
    assert require_branch({'role':'Admin','branch_id':1},3)==3
