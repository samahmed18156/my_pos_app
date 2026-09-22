from pathlib import Path
import zipfile

from services.upgrade_safety import validate_upgrade_safety, validate_upgrade_zip

ROOT = Path(__file__).resolve().parents[1]


def test_phase75_upgrade_safety_passes_current_tree():
    assert validate_upgrade_safety(ROOT) == []


def test_phase75_detects_live_database_in_release_tree(tmp_path):
    for rel in ("packaging/windows/BKPOS.iss", "packaging/windows/BKPOS_Windows10.iss"):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            '#define MyAppVersion "10.0.0"\n'
            'PrivilegesRequired=lowest\n'
            'DefaultDirName={localappdata}\\BKPOS\n'
            'AppId={A3B2C1D0-6F54-4E21-9A87-100000000001}\n',
            encoding="utf-8",
        )
    (tmp_path / "pos_store.db").write_text("live", encoding="utf-8")
    issues = validate_upgrade_safety(tmp_path)
    assert any("Live database" in issue for issue in issues)


def test_phase75_zip_rejects_live_database(tmp_path):
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("BKPOS/packaging/windows/BKPOS.iss", "")
        zf.writestr("BKPOS/packaging/windows/BKPOS_Windows10.iss", "")
        zf.writestr("BKPOS/pos_store.db", "live")
    issues = validate_upgrade_zip(bad)
    assert any("live database" in issue.lower() for issue in issues)


def test_phase75_zip_rejects_unrelated_database(tmp_path):
    bad = tmp_path / "bad2.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("BKPOS/packaging/windows/BKPOS.iss", "")
        zf.writestr("BKPOS/packaging/windows/BKPOS_Windows10.iss", "")
        zf.writestr("BKPOS/sample.sqlite", "db")
    issues = validate_upgrade_zip(bad)
    assert any("database file" in issue.lower() for issue in issues)


def test_phase75_installer_scripts_keep_per_user_identity():
    for name in ("BKPOS.iss", "BKPOS_Windows10.iss"):
        text = (ROOT / "packaging/windows" / name).read_text(encoding="utf-8")
        assert "PrivilegesRequired=lowest" in text
        assert "DefaultDirName={localappdata}\\BKPOS" in text
        assert "pos_store.db" not in text
