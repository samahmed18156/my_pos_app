import json
import os
import sys
from pathlib import Path


def test_lifecycle_state_round_trip(tmp_path, monkeypatch):
    import services.lifecycle_hardening as lh
    monkeypatch.setattr(lh, "LIFECYCLE_DIR", tmp_path / "runtime")
    monkeypatch.setattr(lh, "STATE_PATH", tmp_path / "runtime" / "lifecycle_state.json")

    started = lh.startup_runtime()
    assert started["status"] == "running"
    assert started["previous_clean"] is False
    assert lh.lifecycle_status()["status"] == "running"

    finished = lh.clean_shutdown("test")
    assert finished["status"] == "clean_shutdown"
    assert finished["shutdown_reason"] == "test"
    assert lh.lifecycle_status()["status"] == "clean_shutdown"


def test_unclean_previous_run_is_detected(tmp_path, monkeypatch):
    import services.lifecycle_hardening as lh
    monkeypatch.setattr(lh, "LIFECYCLE_DIR", tmp_path / "runtime")
    monkeypatch.setattr(lh, "STATE_PATH", tmp_path / "runtime" / "lifecycle_state.json")
    lh.LIFECYCLE_DIR.mkdir(parents=True)
    lh.STATE_PATH.write_text(json.dumps({"status": "running", "pid": 123}), encoding="utf-8")

    state = lh.startup_runtime()
    assert state["previous_clean"] is False
    assert state["previous_status"] == "running"


def test_lifecycle_status_is_safe_when_state_missing(tmp_path, monkeypatch):
    import services.lifecycle_hardening as lh
    monkeypatch.setattr(lh, "STATE_PATH", tmp_path / "missing.json")
    status = lh.lifecycle_status()
    assert status["ok"] is False
    assert status["status"] == "unknown"
