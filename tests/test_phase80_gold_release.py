from pathlib import Path
from services.gold_release_gate import APP_NAME, APP_VERSION, EXE_VERSION, validate_tree

ROOT = Path(__file__).resolve().parents[1]


def test_phase80_gold_identity():
    assert APP_NAME == "BKPOS"
    assert APP_VERSION == "10.0.0"
    assert EXE_VERSION == "10.0.0.0"
    assert validate_tree(ROOT) == []


def test_phase80_gold_version_files():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "BKPOS 10.0.0"
    assert (ROOT / "RELEASE_VERSION.txt").read_text(encoding="utf-8").strip() == "BKPOS 10.0.0 Gold Release"


def test_phase80_gold_installers_are_per_user_and_final():
    for name in ("BKPOS.iss", "BKPOS_Windows10.iss"):
        text = (ROOT / "packaging/windows" / name).read_text(encoding="utf-8")
        assert '#define MyAppVersion "10.0.0"' in text
        assert "PrivilegesRequired=lowest" in text
        assert "SetupIconFile=" not in text


def test_phase80_gold_release_script_exists():
    assert (ROOT / "run_phase80_gold_release.py").is_file()
