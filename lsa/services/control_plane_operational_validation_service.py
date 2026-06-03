from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class ControlPlaneOperationalValidationSummary:
    validation_id: str
    executed_at: str
    changed_by: str
    reason: str | None
    environment_name: str
    expected_backend: str
    process_backups: bool
    runtime_rehearsal: dict[str, Any]
    backup_rehearsal: dict[str, Any]
    live_workload_target_validation: dict[str, Any]
    live_workload_drift_proof: dict[str, Any] | None
    backup_export_validation: dict[str, Any]
    backup_validation: dict[str, Any]
    live_workload_proof_validation: dict[str, Any]
    observability_export_validation: dict[str, Any]
    queue_validation: dict[str, Any] | None
    workload_validation: dict[str, Any] | None
    worker_recovery_validation: dict[str, Any] | None
    deployment_readiness: dict[str, Any]
    checks: dict[str, bool]
    status: str
    maintenance_event_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "executed_at": self.executed_at,
            "changed_by": self.changed_by,
            "reason": self.reason,
            "environment_name": self.environment_name,
            "expected_backend": self.expected_backend,
            "process_backups": self.process_backups,
            "runtime_rehearsal": dict(self.runtime_rehearsal),
            "backup_rehearsal": dict(self.backup_rehearsal),
            "live_workload_target_validation": dict(self.live_workload_target_validation),
            "live_workload_drift_proof": None if self.live_workload_drift_proof is None else dict(self.live_workload_drift_proof),
            "backup_export_validation": dict(self.backup_export_validation),
            "backup_validation": dict(self.backup_validation),
            "live_workload_proof_validation": dict(self.live_workload_proof_validation),
            "observability_export_validation": dict(self.observability_export_validation),
            "queue_validation": None if self.queue_validation is None else dict(self.queue_validation),
            "workload_validation": None if self.workload_validation is None else dict(self.workload_validation),
            "worker_recovery_validation": (
                None if self.worker_recovery_validation is None else dict(self.worker_recovery_validation)
            ),
            "deployment_readiness": dict(self.deployment_readiness),
            "checks": dict(self.checks),
            "status": self.status,
            "maintenance_event_id": self.maintenance_event_id,
        }


@dataclass(slots=True)
class ControlPlaneOperationalValidationService:
    settings: Any
    job_service: Any
    runtime_rehearsal_service: Any
    backup_rehearsal_service: Any
    backup_operations_service: Any
    backup_validation_service: Any
    live_workload_drift_proof_service: Any | None
    live_workload_target_validation_service: Any
    live_workload_proof_validation_service: Any
    observability_export_service: Any
    queue_validation_service: Any | None
    workload_validation_service: Any | None
    worker_recovery_validation_service: Any | None
    deployment_readiness_service: Any
    now_factory: Any

    def run(
        self,
        *,
        changed_by: str,
        expected_backend: str = "postgres",
        reason: str | None = None,
        process_backups: bool = True,
        cleanup: bool = True,
        run_queue_validation: bool = True,
        run_live_workload_drift_proof: bool = True,
        queue_success_jobs: int = 2,
        queue_failure_jobs: int = 1,
        queue_delay_seconds: float = 0.0,
        run_inline_queue_worker: bool = True,
        run_workload_validation: bool = True,
        workload_rounds: int = 3,
        workload_maintenance_pause_jobs: int = 3,
        inject_maintenance_mode_pause: bool = True,
        run_worker_recovery_validation: bool = True,
        actor_details: dict | None = None,
        target_profile_name: str | None = None,
    ) -> ControlPlaneOperationalValidationSummary:
        validation_id = uuid4().hex[:12]
        executed_at = self.now_factory()

        if process_backups:
            self.backup_operations_service.process_scheduled_backups(
                changed_by=changed_by,
                reason=reason or "operational validation backup refresh",
                force=True,
                actor_details=actor_details,
            )

        runtime_rehearsal = self.runtime_rehearsal_service.run(
            changed_by=changed_by,
            expected_backend=expected_backend,
            reason=reason,
            cleanup=cleanup,
            ignore_deployment_readiness=True,
            actor_details=actor_details,
        ).to_dict()
        backup_rehearsal = self.backup_rehearsal_service.run(
            changed_by=changed_by,
            reason=reason,
            cleanup=cleanup,
            actor_details=actor_details,
        ).to_dict()
        live_workload_target_validation = self.live_workload_target_validation_service.execute(
            changed_by=changed_by,
            reason=reason or "operational validation target probe",
            actor_details=actor_details,
            target_profile_name=target_profile_name,
        ).to_dict()
        live_workload_drift_proof = None
        if run_live_workload_drift_proof and self.live_workload_drift_proof_service is not None:
            live_workload_drift_proof = self.live_workload_drift_proof_service.run(
                changed_by=changed_by,
                reason=reason,
                persist=True,
                actor_details=actor_details,
                target_profile_name=target_profile_name,
            ).to_dict()
        backup_export_validation = self.backup_operations_service.latest_backup_export_validation().to_dict()
        backup_validation = self.backup_validation_service.build_summary().to_dict()
        live_workload_proof_validation = self.live_workload_proof_validation_service.build_summary().to_dict()
        self.observability_export_service.export_snapshot(
            changed_by=changed_by,
            reason=reason or "operational validation observability export",
            actor_details=actor_details,
        )
        observability_export_validation = self.observability_export_service.latest_export_validation().to_dict()
        queue_validation = None
        if run_queue_validation and self.queue_validation_service is not None:
            queue_validation = self.queue_validation_service.run(
                changed_by=changed_by,
                reason=reason,
                success_jobs=queue_success_jobs,
                failure_jobs=queue_failure_jobs,
                delay_seconds=queue_delay_seconds,
                run_inline_worker=run_inline_queue_worker,
                actor_details=actor_details,
            ).to_dict()
        workload_validation = None
        if run_workload_validation and self.workload_validation_service is not None:
            workload_validation = self.workload_validation_service.run(
                changed_by=changed_by,
                reason=reason,
                rounds=workload_rounds,
                queue_success_jobs=queue_success_jobs,
                queue_failure_jobs=queue_failure_jobs,
                queue_delay_seconds=queue_delay_seconds,
                inject_maintenance_mode_pause=inject_maintenance_mode_pause,
                maintenance_pause_jobs=workload_maintenance_pause_jobs,
                run_inline_queue_worker=run_inline_queue_worker,
                actor_details=actor_details,
            ).to_dict()
        worker_recovery_validation = None
        if run_worker_recovery_validation and self.worker_recovery_validation_service is not None:
            worker_recovery_validation = self.worker_recovery_validation_service.run(
                changed_by=changed_by,
                reason=reason,
                actor_details=actor_details,
            ).to_dict()
        deployment_readiness = self.deployment_readiness_service.evaluate().to_dict()

        checks = {
            "runtime_rehearsal_passed": runtime_rehearsal.get("status") == "passed",
            "backup_rehearsal_passed": backup_rehearsal.get("status") == "passed",
            "live_workload_target_validation_passed": live_workload_target_validation.get("status") == "passed",
            "live_workload_drift_proof_passed": (
                True if live_workload_drift_proof is None else bool(live_workload_drift_proof.get("passed"))
            ),
            "backup_export_validation_passed": backup_export_validation.get("status") == "passed",
            "backup_validation_passed": backup_validation.get("status") == "passed",
            "live_workload_proof_validation_passed": live_workload_proof_validation.get("status") == "passed",
            "observability_export_validation_passed": observability_export_validation.get("status") == "passed",
            "queue_validation_passed": True if queue_validation is None else queue_validation.get("status") == "passed",
            "workload_validation_passed": True if workload_validation is None else workload_validation.get("status") == "passed",
            "worker_recovery_validation_passed": (
                True if worker_recovery_validation is None else worker_recovery_validation.get("status") == "passed"
            ),
            "deployment_readiness_ready": bool(deployment_readiness.get("ready")),
        }
        status = "passed" if all(checks.values()) else "failed"

        summary = ControlPlaneOperationalValidationSummary(
            validation_id=validation_id,
            executed_at=executed_at,
            changed_by=changed_by,
            reason=reason,
            environment_name=self.settings.environment_name,
            expected_backend=expected_backend,
            process_backups=process_backups,
            runtime_rehearsal=runtime_rehearsal,
            backup_rehearsal=backup_rehearsal,
            live_workload_target_validation=live_workload_target_validation,
            live_workload_drift_proof=live_workload_drift_proof,
            backup_export_validation=backup_export_validation,
            backup_validation=backup_validation,
            live_workload_proof_validation=live_workload_proof_validation,
            observability_export_validation=observability_export_validation,
            queue_validation=queue_validation,
            workload_validation=workload_validation,
            worker_recovery_validation=worker_recovery_validation,
            deployment_readiness=deployment_readiness,
            checks=checks,
            status=status,
        )
        event = self.job_service.record_maintenance_event(
            event_type="control_plane_operational_validation_executed",
            changed_by=changed_by,
            reason=reason,
            details=summary.to_dict(),
            actor_details=actor_details,
        )
        summary.maintenance_event_id = event.event_id
        return summary
