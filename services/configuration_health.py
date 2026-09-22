"""BKPOS Phase 64 — configuration/deployment health checks."""
from __future__ import annotations

from dataclasses import dataclass

from core.deployment_config import deployment_summary, resolve_paths, validate_deployment_paths


@dataclass(frozen=True)
class ConfigurationCheck:
    name: str
    status: str
    message: str

    @property
    def ok(self) -> bool:
        return self.status == "OK"


def run_configuration_health() -> list[ConfigurationCheck]:
    """Return non-mutating checks for the active deployment configuration."""
    paths = resolve_paths()
    issues = validate_deployment_paths(paths)
    return [
        ConfigurationCheck(
            "deployment_paths",
            "OK" if not issues else "FAIL",
            "Deployment path policy is valid." if not issues else "; ".join(issues),
        ),
        ConfigurationCheck(
            "application_data_separation",
            "OK" if paths.database_path.parent == paths.data_dir else "FAIL",
            "Database is located inside the configured BKPOS data directory.",
        ),
    ]


def configuration_health_ok() -> bool:
    return all(check.ok for check in run_configuration_health())


def configuration_report() -> dict:
    checks = run_configuration_health()
    return {
        "deployment": deployment_summary(),
        "ok": all(check.ok for check in checks),
        "checks": [
            {"name": c.name, "status": c.status, "message": c.message}
            for c in checks
        ],
    }
