from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "packaging" / "windows"


def test_bkpos_packaging_files_exist():
    required = [
        "MAKE_BKPOS_INSTALLER.bat",
        "build_bkpos_windows10.bat",
        "build_bkpos_legacy.bat",
        "BKPOS_Windows10.spec",
        "BKPOS_Windows10.iss",
        "BKPOS.spec",
        "BKPOS.iss",
        "CREATE_BKPOS_DESKTOP_SHORTCUT.bat",
        "README_WINDOWS_DESKTOP_BUILD.md",
    ]
    assert all((PACK / name).is_file() for name in required)


def test_legacy_mipos_packaging_definitions_removed():
    legacy = [
        "MAKE_MIPOS_INSTALLER.bat",
        "MiPOS.iss",
        "MiPOS.spec",
        "MiPOS_Windows10.iss",
        "MiPOS_Windows10.spec",
        "build_windows.bat",
        "build_windows10.bat",
        "CREATE_DESKTOP_SHORTCUT.bat",
    ]
    assert not any((PACK / name).exists() for name in legacy)


def test_windows10_installer_is_bkpos_and_per_user():
    iss = (PACK / "BKPOS_Windows10.iss").read_text()
    assert 'AppName={#MyAppName}' in iss
    assert '#define MyAppName "BKPOS"' in iss
    assert '#define MyAppExeName "BKPOS.exe"' in iss
    assert 'DefaultDirName={localappdata}\\BKPOS' in iss
    assert 'PrivilegesRequired=lowest' in iss
    assert 'OutputBaseFilename=BKPOS_Setup_Windows10' in iss
    assert 'AppId={{A3B2C1D0-6F54-4E21-9A87-100000000001}}' in iss


def test_pyinstaller_output_is_bkpos():
    spec = (PACK / "BKPOS_Windows10.spec").read_text()
    assert 'name="BKPOS"' in spec
    assert 'str(PROJECT / "app.py")' in spec


def test_clean_distribution_manifest_blocks_runtime_artifacts():
    manifest = (ROOT / "CLEAN_DISTRIBUTION_MANIFEST.txt").read_text()
    for item in ("pos_store.db", "generated/", "logs/", "__pycache__/", "*.pyc"):
        assert item in manifest


def test_legacy_installer_is_explicitly_legacy():
    iss = (PACK / "BKPOS.iss").read_text()
    assert "MinVersion=6.1" in iss
    assert "OutputBaseFilename=BKPOS_Setup_Legacy" in iss
    assert "PrivilegesRequired=lowest" in iss


def test_release_source_tree_has_no_runtime_artifacts():
    forbidden_dirs = {".idea", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
                      "build", "dist", "output", "generated", "logs", "backups", "receipts",
                      "diagnostics", "runtime"}
    forbidden_files = {"pos_store.db", "pos_store.sqlite", "pos_store.sqlite3"}
    violations = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if any(part.lower() in forbidden_dirs for part in rel.parts):
            violations.append(str(rel))
        elif path.is_file() and (path.name.lower() in forbidden_files or path.suffix.lower() in {".pyc", ".pyo"}):
            violations.append(str(rel))
    assert violations == []
