"""BKPOS Phase 74 — deterministic release artifact gate."""
from __future__ import annotations

from pathlib import Path
import zipfile

from core.release_identity import APP_NAME, APP_VERSION, EXE_VERSION, INSTALLER_APP_ID, validate_release_identity

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_RELEASE_NAMES = {
    "pos_store.db", "pos_store.sqlite", "pos_store.sqlite3",
    ".pytest_cache", "__pycache__", ".idea", ".mypy_cache", ".ruff_cache",
    "build", "dist", "output", "generated", "logs", "diagnostics",
    "receipts", "backups", "runtime",
}
REQUIRED_RELEASE_FILES = (
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
)


def validate_release_tree(root: Path = ROOT) -> list[str]:
    issues: list[str] = []
    for rel in REQUIRED_RELEASE_FILES:
        if not (root / rel).is_file():
            issues.append(f"Missing required release file: {rel}")

    issues.extend(validate_release_identity())

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        parts = {p.lower() for p in path.relative_to(root).parts}
        if path.name.lower() == "pos_store.db" or parts & {x.lower() for x in FORBIDDEN_RELEASE_NAMES}:
            issues.append(f"Forbidden release artifact: {path.relative_to(root)}")
        if path.suffix.lower() in {".pyc", ".pyo"}:
            issues.append(f"Bytecode must not ship: {path.relative_to(root)}")
    return sorted(set(issues))


def validate_release_zip(zip_path: str | Path) -> list[str]:
    """Validate a built release ZIP without extracting or modifying it."""
    path = Path(zip_path)
    issues: list[str] = []
    if not path.is_file():
        return [f"Release ZIP not found: {path}"]
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            lowered = [n.lower().replace("\\", "/") for n in names]
            for required in REQUIRED_RELEASE_FILES:
                if not any(n.endswith(required.lower()) for n in lowered):
                    issues.append(f"ZIP missing required file: {required}")
            for name in lowered:
                parts = set(name.split("/"))
                if "pos_store.db" in parts or any(p in parts for p in FORBIDDEN_RELEASE_NAMES):
                    issues.append(f"ZIP contains forbidden artifact: {name}")
                if name.endswith(".pyc") or name.endswith(".pyo"):
                    issues.append(f"ZIP contains bytecode: {name}")
            # Ensure the ZIP has a sane BKPOS identity in its metadata files.
            version_entries = [n for n in names if n.lower().endswith("version.txt") or n.lower().endswith("release_version.txt")]
            if not version_entries:
                issues.append("ZIP contains no release version metadata.")
            else:
                text = "\n".join(zf.read(n).decode("utf-8", errors="replace") for n in version_entries)
                if APP_NAME not in text or APP_VERSION not in text:
                    issues.append("ZIP release version metadata is inconsistent.")
    except zipfile.BadZipFile:
        issues.append(f"Invalid ZIP archive: {path}")
    return sorted(set(issues))


def release_gate_summary(zip_path: str | Path | None = None) -> dict[str, object]:
    tree_issues = validate_release_tree()
    zip_issues = validate_release_zip(zip_path) if zip_path else []
    return {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "exe_version": EXE_VERSION,
        "installer_app_id": INSTALLER_APP_ID,
        "tree_ok": not tree_issues,
        "zip_ok": not zip_issues if zip_path else None,
        "issues": tree_issues + zip_issues,
    }
