from pathlib import Path

from core.release_identity import (
    APP_VERSION as CURRENT_APP_VERSION,
    APP_NAME,
    APP_VERSION,
    EXE_VERSION,
    INSTALLER_APP_ID,
    validate_release_identity,
)

ROOT = Path(__file__).resolve().parents[1]
WIN = ROOT / "packaging" / "windows"


def test_release_identity_is_consistent():
    assert APP_NAME == "BKPOS"
    assert APP_VERSION == CURRENT_APP_VERSION
    assert EXE_VERSION == "10.0.0.0"
    assert INSTALLER_APP_ID == "{A3B2C1D0-6F54-4E21-9A87-100000000001}"
    assert validate_release_identity() == []


def test_version_files_match_release_identity():
    assert APP_VERSION in (ROOT / "VERSION.txt").read_text(encoding="utf-8")
    assert APP_VERSION in (ROOT / "RELEASE_VERSION.txt").read_text(encoding="utf-8")


def test_installers_do_not_reference_missing_external_icon():
    for name in ("BKPOS.iss", "BKPOS_Windows10.iss"):
        text = (WIN / name).read_text(encoding="utf-8")
        assert "SetupIconFile=" not in text
        assert "PrivilegesRequired=lowest" in text
