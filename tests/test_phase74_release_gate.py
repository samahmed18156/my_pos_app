from pathlib import Path
import zipfile

from services.release_gate import (
    APP_NAME,
    APP_VERSION,
    EXE_VERSION,
    validate_release_tree,
    validate_release_zip,
)

ROOT = Path(__file__).resolve().parents[1]


def test_phase74_release_identity_is_present():
    assert APP_NAME == "BKPOS"
    assert APP_VERSION == "10.0.0"
    assert EXE_VERSION == "10.0.0.0"
    assert (ROOT / "app.py").is_file()
    assert (ROOT / "packaging/windows/BKPOS.iss").is_file()


def test_phase74_release_tree_detects_forbidden_artifact(tmp_path):
    for rel in (
        "app.py",
        "core/release_identity.py",
        "core/deployment_config.py",
        "packaging/windows/BKPOS.iss",
        "packaging/windows/BKPOS_Windows10.iss",
        "packaging/windows/BKPOS.spec",
        "packaging/windows/BKPOS_Windows10.spec",
        "packaging/windows/BKPOS_version_info.txt",
        "VERSION.txt",
        "RELEASE_VERSION.txt",
    ):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("BKPOS 10.0.0", encoding="utf-8")
    (tmp_path / "pos_store.db").write_text("forbidden", encoding="utf-8")
    issues = validate_release_tree(tmp_path)
    assert any("pos_store.db" in issue for issue in issues)


def test_phase74_zip_gate_rejects_database(tmp_path):
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("BKPOS/VERSION.txt", "BKPOS 10.0.0")
        zf.writestr("BKPOS/RELEASE_VERSION.txt", "BKPOS 10.0.0")
        zf.writestr("BKPOS/pos_store.db", "not a live database")
    issues = validate_release_zip(bad)
    assert any("pos_store.db" in issue for issue in issues)


def test_phase74_release_gate_script_exists():
    assert (ROOT / "run_phase74_release_gate.py").is_file()
