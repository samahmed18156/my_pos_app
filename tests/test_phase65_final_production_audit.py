from pathlib import Path

from services.final_production_audit import audit_packaging, audit_source_tree, audit_versions, run_final_audit

ROOT = Path(__file__).resolve().parents[1]


def test_phase65_source_gate_passes():
    checks = audit_source_tree(ROOT)
    assert all(c.ok for c in checks), [(c.name, c.message) for c in checks if not c.ok]


def test_phase65_packaging_gate_passes():
    checks = audit_packaging(ROOT)
    assert all(c.ok for c in checks), [(c.name, c.message) for c in checks if not c.ok]


def test_phase65_version_gate_passes():
    checks = audit_versions(ROOT)
    assert all(c.ok for c in checks), [(c.name, c.message) for c in checks if not c.ok]


def test_phase65_final_gate_passes():
    result = run_final_audit(ROOT)
    assert result["ok"], [(c.name, c.message) for c in result["checks"] if not c.ok]
    assert result["app_name"] == "BKPOS"
