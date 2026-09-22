from pathlib import Path

import core.deployment_config as deployment_config
from services.configuration_health import configuration_health_ok, configuration_report


def test_source_paths_keep_database_inside_project(monkeypatch):
    monkeypatch.setattr(deployment_config.sys, "frozen", False, raising=False)
    paths = deployment_config.resolve_paths()
    assert paths.data_dir == paths.app_base_dir
    assert paths.database_path.parent == paths.data_dir


def test_packaged_paths_separate_app_and_data(monkeypatch, tmp_path):
    exe = tmp_path / "BKPOS" / "BKPOS.exe"
    exe.parent.mkdir(parents=True)
    monkeypatch.setattr(deployment_config.sys, "frozen", True, raising=False)
    monkeypatch.setattr(deployment_config.sys, "executable", str(exe), raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    paths = deployment_config.resolve_paths()
    assert paths.app_base_dir == exe.parent
    assert paths.data_dir == tmp_path / "Roaming" / "BKPOS"
    assert paths.app_base_dir != paths.data_dir
    assert paths.database_path.parent == paths.data_dir


def test_deployment_summary_is_safe_and_branded(monkeypatch):
    monkeypatch.setattr(deployment_config.sys, "frozen", False, raising=False)
    summary = deployment_config.deployment_summary()
    assert summary["app_name"] == "BKPOS"
    assert "database_path" in summary
    assert "password" not in " ".join(summary).lower()


def test_configuration_health_passes_in_source_mode(monkeypatch):
    monkeypatch.setattr(deployment_config.sys, "frozen", False, raising=False)
    assert configuration_health_ok()
    report = configuration_report()
    assert report["ok"] is True
    assert all(item["status"] == "OK" for item in report["checks"])
