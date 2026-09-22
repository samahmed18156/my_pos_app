from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIN = ROOT / "packaging" / "windows"

def test_installer_identity_and_version():
    for name in ("BKPOS.iss", "BKPOS_Windows10.iss"):
        text=(WIN/name).read_text(encoding="utf-8")
        assert 'MyAppName "BKPOS"' in text
        assert 'MyAppVersion "10.0.0"' in text
        assert 'PrivilegesRequired=lowest' in text
        assert 'OutputBaseFilename=BKPOS_Setup_' in text

def test_desktop_shortcut_is_optional():
    text=(WIN/"BKPOS_Windows10.iss").read_text(encoding="utf-8")
    assert '[Tasks]' in text
    assert 'desktopicon' in text
    assert 'Flags: unchecked' in text

def test_version_metadata_is_present():
    text=(WIN/"BKPOS_version_info.txt").read_text(encoding="utf-8")
    assert "FileDescription','BKPOS Point of Sale" in text
    assert "OriginalFilename','BKPOS.exe" in text

def test_specs_reference_version_metadata():
    for name in ("BKPOS.spec", "BKPOS_Windows10.spec"):
        text=(WIN/name).read_text(encoding="utf-8")
        assert 'BKPOS_version_info.txt' in text
