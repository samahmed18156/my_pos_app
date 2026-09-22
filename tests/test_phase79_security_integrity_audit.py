from pathlib import Path

from services.final_security_integrity_audit import validate_security_integrity_gate

ROOT = Path(__file__).resolve().parents[1]


def test_phase79_gate_passes_current_tree():
    assert validate_security_integrity_gate(ROOT) == []


def test_phase79_detects_missing_security_file(tmp_path):
    issues = validate_security_integrity_gate(tmp_path)
    assert any("Missing security/integrity file" in x for x in issues)


def test_phase79_cashier_cannot_use_admin_controls():
    from core.permissions import has_permission
    for permission in ("backup_restore", "user_management", "stock_adjustment", "price_change"):
        assert not has_permission("cashier", permission)


def test_phase79_manager_and_admin_boundaries():
    from core.permissions import has_permission
    assert has_permission("admin", "user_management")
    assert has_permission("manager", "grn")
    assert not has_permission("manager", "user_management")


def test_phase79_audit_log_is_protected():
    text = (ROOT / "audit_log.py").read_text(encoding="utf-8")
    assert "trg_audit_log_no_update" in text
    assert "trg_audit_log_no_delete" in text


def test_phase79_does_not_allow_external_database_artifacts():
    assert not (ROOT / "pos_store.db").exists()
