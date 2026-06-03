from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from lsa.services.control_plane_deployment_readiness_service import ControlPlaneDeploymentReadinessService
from lsa.services.control_plane_runtime_smoke_service import ControlPlaneRuntimeSmokeService
from lsa.settings import postgres_runtime_enabled


@dataclass(slots=True)
class ControlPlaneRuntimeRehearsalSummary:
    rehearsal_id: str
    executed_at: str
    changed_by: str
    reason: str | None
    environment_name: str
    expected_backend: str
    database_backend: str
    snapshot_repository_backend: str
    audit_repository_backend: str
    job_repository_backend: str
    postgres_runtime_enabled: bool
    postgres_runtime_active: bool
    database_runtime_available: bool
    database_runtime_blockers: list[str]
    deployment_readiness: dict[str, Any]
    checks: dict[str, bool]
    status: str
    smoke: dict[str, Any]
    maintenance_event_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rehearsal_id": self.rehearsal_id,
            "executed_at": self.executed_at,
            "changed_by": self.changed_by,
            "reason": self.reason,
            "environment_name": self.environment_name,
            "expected_backend": self.expected_backend,
            "database_backend": self.database_backend,
            "snapshot_repository_backend": self.snapshot_repository_backend,
            "audit_repository_backend": self.audit_repository_backend,
            "job_repository_backend": self.job_repository_backend,
            "postgres_runtime_enabled": self.postgres_runtime_enabled,
            "postgres_runtime_active": self.postgres_runtime_active,
            "database_runtime_available": self.database_runtime_available,
            "database_runtime_blockers": list(self.database_runtime_blockers),
            "deployment_readiness": dict(self.deployment_readiness),
            "checks": dict(self.checks),
            "status": self.status,
            "smoke": dict(self.smoke),
            "maintenance_event_id": self.maintenance_event_id,
        }


@dataclass(slots=True)
class ControlPlaneRuntimeRehearsalService:
    settings: Any
    job_repository: Any
    job_service: Any
    runtime_smoke_service: ControlPlaneRuntimeSmokeService
    now_factory: Any

    def run(
        self,
        *,
        changed_by: str,
        expected_backend: str,
        reason: str | None = None,
        cleanup: bool = True,
        ignore_deployment_readiness: bool = False,
        actor_details: dict | None = None,
    ) -> ControlPlaneRuntimeRehearsalSummary:
        rehearsal_id = uuid4().hex[:12]
        executed_at = self.now_factory()
        database_status = self.job_repository.database_status()
        deployment_readiness = ControlPlaneDeploymentReadinessService(
            settings=self.settings,
            job_repository=self.job_repository,
            job_service=self.job_service,
        ).evaluate()
        if (
            self.settings.runtime_rehearsal_deployment_readiness_required
            and not ignore_deployment_readiness
            and not deployment_readiness.ready
        ):
            raise ValueError(
                "Runtime rehearsal blocked by deployment readiness: "
                + ", ".join(sorted(deployment_readiness.blockers))
            )
        smoke_summary = self.runtime_smoke_service.run(
            changed_by=changed_by,
            reason=reason,
            cleanup=cleanup,
            actor_details=actor_details,
        )
        smoke_payload = smoke_summary.to_dict()

        postgres_runtime_active = (
            smoke_summary.snapshot_repository_backend == "postgres"
            and smoke_summary.audit_repository_backend == "postgres"
            and smoke_summary.job_repository_backend == "postgres"
        )
        checks = {
            "database_backend_matches_expected": str(database_status["backend"]) == expected_backend,
            "snapshot_repository_backend_matches_expected": smoke_summary.snapshot_repository_backend == expected_backend,
            "audit_repository_backend_matches_expected": smoke_summary.audit_repository_backend == expected_backend,
            "job_repository_backend_matches_expected": smoke_summary.job_repository_backend == expected_backend,
            "database_runtime_available": bool(database_status["runtime_available"]),
            "deployment_readiness_ok": True if ignore_deployment_readiness else deployment_readiness.ready,
            "postgres_runtime_active_matches_expected": (
                postgres_runtime_active if expected_backend == "postgres" else not postgres_runtime_active
            ),
            "smoke_snapshot_round_trip_ok": smoke_summary.snapshot_round_trip_ok,
            "smoke_audit_round_trip_ok": smoke_summary.audit_round_trip_ok,
            "smoke_job_round_trip_ok": smoke_summary.job_round_trip_ok,
            "smoke_cleanup_satisfied": (not cleanup) or smoke_summary.cleanup_completed,
        }
        status = "passed" if all(checks.values()) else "failed"

        summary = ControlPlaneRuntimeRehearsalSummary(
            rehearsal_id=rehearsal_id,
            executed_at=executed_at,
            changed_by=changed_by,
            reason=reason,
            environment_name=self.settings.environment_name,
            expected_backend=expected_backend,
            database_backend=str(database_status["backend"]),
            snapshot_repository_backend=smoke_summary.snapshot_repository_backend,
            audit_repository_backend=smoke_summary.audit_repository_backend,
            job_repository_backend=smoke_summary.job_repository_backend,
            postgres_runtime_enabled=postgres_runtime_enabled(self.settings),
            postgres_runtime_active=postgres_runtime_active,
            database_runtime_available=bool(database_status["runtime_available"]),
            database_runtime_blockers=[str(item) for item in database_status["runtime_blockers"]],
            deployment_readiness=deployment_readiness.to_dict(),
            checks=checks,
            status=status,
            smoke=smoke_payload,
        )
        event = self.job_service.record_maintenance_event(
            event_type="control_plane_runtime_rehearsal_executed",
            changed_by=changed_by,
            reason=reason,
            details=summary.to_dict(),
            actor_details=actor_details,
        )
        summary.maintenance_event_id = event.event_id
        return summary
