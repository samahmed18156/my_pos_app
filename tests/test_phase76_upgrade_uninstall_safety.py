from pathlib import Path

from services.upgrade_uninstall_safety import validate_installer_data_protection

ROOT = Path(__file__).resolve().parents[1]


def test_phase76_current_installers_protect_user_data():
    assert validate_installer_data_protection(ROOT) == []


def test_phase76_detects_uninstall_delete_section(tmp_path):
    for rel in ("packaging/windows/BKPOS.iss", "packaging/windows/BKPOS_Windows10.iss"):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            '#define MyAppVersion "10.0.0"\n'
            'AppId={A3B2C1D0-6F54-4E21-9A87-100000000001}\n'
            'DefaultDirName={localappdata}\\BKPOS\n'
            'PrivilegesRequired=lowest\n'
            '[UninstallDelete]\n'
            'Type: filesandordirs; Name: "{userappdata}\\BKPOS"\n'
            '[Icons]\n'
            'Name: "{group}\\BKPOS Data Folder"; Filename: "{userappdata}\\BKPOS"\n',
            encoding="utf-8",
        )
    issues = validate_installer_data_protection(tmp_path)
    assert any("UninstallDelete" in issue for issue in issues)


def test_phase76_detects_live_database_reference(tmp_path):
    for rel in ("packaging/windows/BKPOS.iss", "packaging/windows/BKPOS_Windows10.iss"):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            '#define MyAppVersion "10.0.0"\n'
            'AppId={A3B2C1D0-6F54-4E21-9A87-100000000001}\n'
            'DefaultDirName={localappdata}\\BKPOS\n'
            'PrivilegesRequired=lowest\n'
            '[Icons]\n'
            'Name: "{group}\\BKPOS Data Folder"; Filename: "{userappdata}\\BKPOS"\n'
            'Source: "pos_store.db"; DestDir: "{userappdata}\\BKPOS"\n',
            encoding="utf-8",
        )
    issues = validate_installer_data_protection(tmp_path)
    assert any("pos_store.db" in issue for issue in issues)
