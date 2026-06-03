from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from lsa.services.control_plane_backup_operations_service import ControlPlaneBackupOperationsService
from lsa.services.control_plane_backup_service import ControlPlaneBackupService, ControlPlaneBackupSummary
from lsa.services.control_plane_backup_validation_service import ControlPlaneBackupValidationService
from lsa.services.control_plane_live_workload_proof_validation_service import (
    ControlPlaneLiveWorkloadProofValidationService,
)
from lsa.services.control_plane_live_workload_target_validation_service import (
    ControlPlaneLiveWorkloadTargetValidationService,
)
from lsa.services.control_plane_observability_export_service import ControlPlaneObservabilityExportService
from lsa.services.control_plane_deployment_readiness_service import ControlPlaneDeploymentReadinessService
from lsa.services.job_service import JobService
from lsa.services.control_plane_runtime_validation_review_service import ControlPlaneRuntimeValidationReviewService
from lsa.services.control_plane_runtime_validation_service import ControlPlaneRuntimeValidationService
from lsa.services.runtime_validation_policy import RuntimeValidationPolicy, load_runtime_validation_policy_bundle
from lsa.storage.files import JobRepository


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class ControlPlaneMaintenancePreflight:
    generated_at: str
    environment_name: str
    worker_mode: str
    maintenance_mode_active: bool
    maintenance_mode_changed_at: str | None
    maintenance_mode_changed_by: str | None
    maintenance_mode_reason: str | None
    database_backend: str
    database_url: str
    database_path: str
    database_ready: bool
    database_writable: bool
    database_schema_version: int
    database_expected_schema_version: int
    database_schema_ready: bool
    database_pending_migration_count: int
    worker_running: bool
    active_workers: int
    queued_jobs: int
    running_jobs: int
    completed_jobs: int
    failed_jobs: int
    runtime_validation: dict[str, Any]
    live_workload_target_validation: dict[str, Any]
    live_workload_proof_validation: dict[str, Any]
    backup_validation: dict[str, Any]
    backup_export_validation: dict[str, Any]
    observability_export_validation: dict[str, Any]
    deployment_readiness: dict[str, Any]
    runtime_validation_change_control_requests: list[dict[str, Any]] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def can_execute(self) -> bool:
        return not self.blockers

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "environment_name": self.environment_name,
            "worker_mode": self.worker_mode,
            "maintenance_mode_active": self.maintenance_mode_active,
            "maintenance_mode_changed_at": self.maintenance_mode_changed_at,
            "maintenance_mode_changed_by": self.maintenance_mode_changed_by,
            "maintenance_mode_reason": self.maintenance_mode_reason,
            "database_backend": self.database_backend,
            "database_url": self.database_url,
            "database_path": self.database_path,
            "database_ready": self.database_ready,
            "database_writable": self.database_writable,
            "database_schema_version": self.database_schema_version,
            "database_expected_schema_version": self.database_expected_schema_version,
            "database_schema_ready": self.database_schema_ready,
            "database_pending_migration_count": self.database_pending_migration_count,
            "worker_running": self.worker_running,
            "active_workers": self.active_workers,
            "queued_jobs": self.queued_jobs,
            "running_jobs": self.running_jobs,
            "completed_jobs": self.completed_jobs,
            "failed_jobs": self.failed_jobs,
            "runtime_validation": dict(self.runtime_validation),
            "live_workload_target_validation": dict(self.live_workload_target_validation),
            "live_workload_proof_validation": dict(self.live_workload_proof_validation),
            "backup_validation": dict(self.backup_validation),
            "backup_export_validation": dict(self.backup_export_validation),
            "observability_export_validation": dict(self.observability_export_validation),
            "deployment_readiness": dict(self.deployment_readiness),
            "runtime_validation_change_control_requests": [
                dict(item) for item in self.runtime_validation_change_control_requests
            ],
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "can_execute": self.can_execute,
        }


@dataclass(slots=True)
class ControlPlaneMaintenanceWorkflowSummary:
    started_at: str
    completed_at: str
    changed_by: str
    reason: str | None
    backup_path: str
    disable_maintenance_on_success: bool
    maintenance_enabled_by_workflow: bool
    steps: list[str]
    preflight: ControlPlaneMaintenancePreflight
    maintenance_before: dict[str, Any]
    maintenance_after_enable: dict[str, Any] | None
    maintenance_final: dict[str, Any]
    backup: ControlPlaneBackupSummary
    schema_status: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "changed_by": self.changed_by,
            "reason": self.reason,
            "backup_path": self.backup_path,
            "disable_maintenance_on_success": self.disable_maintenance_on_success,
            "maintenance_enabled_by_workflow": self.maintenance_enabled_by_workflow,
            "steps": list(self.steps),
            "preflight": self.preflight.to_dict(),
            "maintenance_before": dict(self.maintenance_before),
            "maintenance_after_enable": None
            if self.maintenance_after_enable is None
            else dict(self.maintenance_after_enable),
            "maintenance_final": dict(self.maintenance_final),
            "backup": self.backup.to_dict(),
            "schema_status": dict(self.schema_status),
        }


@dataclass(slots=True)
class ControlPlaneMaintenanceService:
    settings: Any
    job_repository: JobRepository
    job_service: JobService
    backup_service: ControlPlaneBackupService
    worker_mode: str

    def build_preflight(self) -> ControlPlaneMaintenancePreflight:
        database_status = self.job_repository.database_status()
        maintenance_status = self.job_repository.maintenance_mode_status()
        worker_running = self.job_service.is_worker_running()
        active_workers = self.job_service.active_worker_count()
        queued_jobs = self.job_service.count_jobs_by_status("queued")
        running_jobs = self.job_service.count_jobs_by_status("running")
        completed_jobs = self.job_service.count_jobs_by_status("completed")
        failed_jobs = self.job_service.count_jobs_by_status("failed")
        runtime_policy_bundle = load_runtime_validation_policy_bundle(
            self.settings.runtime_validation_policy_path
        )
        runtime_policy = runtime_policy_bundle.resolve(
            environment_name=self.settings.environment_name,
            fallback=RuntimeValidationPolicy(
                due_soon_age_hours=self.settings.analytics_runtime_rehearsal_due_soon_age_hours,
                warning_age_hours=self.settings.analytics_runtime_rehearsal_warning_age_hours,
                critical_age_hours=self.settings.analytics_runtime_rehearsal_critical_age_hours,
            ),
        )
        runtime_validation = ControlPlaneRuntimeValidationService(
            job_repository=self.job_repository,
            environment_name=self.settings.environment_name,
            due_soon_age_hours=runtime_policy.due_soon_age_hours
            or self.settings.analytics_runtime_rehearsal_due_soon_age_hours,
            warning_age_hours=runtime_policy.warning_age_hours
            or self.settings.analytics_runtime_rehearsal_warning_age_hours,
            critical_age_hours=runtime_policy.critical_age_hours
            or self.settings.analytics_runtime_rehearsal_critical_age_hours,
            policy_source=runtime_policy_bundle.source_for(environment_name=self.settings.environment_name),
        ).build_summary()
        live_workload_target_validation = ControlPlaneLiveWorkloadTargetValidationService(
            settings=self.settings,
            job_repository=self.job_repository,
            job_service=self.job_service,
            live_workload_drift_proof_service=None,
        ).build_summary()
        live_workload_proof_validation = ControlPlaneLiveWorkloadProofValidationService(
            job_repository=self.job_repository,
            environment_name=self.settings.environment_name,
            due_soon_age_hours=self.settings.analytics_live_workload_proof_due_soon_age_hours,
            warning_age_hours=self.settings.analytics_live_workload_proof_warning_age_hours,
            critical_age_hours=self.settings.analytics_live_workload_proof_critical_age_hours,
        ).build_summary()
        backup_validation = ControlPlaneBackupValidationService(
            job_repository=self.job_repository,
            environment_name=self.settings.environment_name,
            due_soon_age_hours=self.settings.analytics_backup_rehearsal_due_soon_age_hours,
            warning_age_hours=self.settings.analytics_backup_rehearsal_warning_age_hours,
            critical_age_hours=self.settings.analytics_backup_rehearsal_critical_age_hours,
        ).build_summary()
        backup_export_validation = ControlPlaneBackupOperationsService(
            settings=self.settings,
            backup_service=self.backup_service,
            job_repository=self.job_repository,
            job_service=self.job_service,
        ).latest_backup_export_validation()
        observability_export_validation = ControlPlaneObservabilityExportService(
            settings=self.settings,
            job_service=self.job_service,
            analytics_service=None,
            metrics_service=None,
            privileged_api_audit_service=None,
        ).latest_export_validation()
        review_service = ControlPlaneRuntimeValidationReviewService(
            settings=self.settings,
            job_service=self.job_service,
            job_repository=self.job_repository,
        )
        deployment_readiness = ControlPlaneDeploymentReadinessService(
            settings=self.settings,
            job_repository=self.job_repository,
            job_service=self.job_service,
        ).evaluate()
        runtime_validation_change_control_requests = [
            request.to_dict()
            for request in review_service.list_change_control_requests(owner_team=None)
            if request.environment_name == self.settings.environment_name
            and request.status in {"pending_review", "rejected"}
        ]
        pending_change_control_requests = [
            request for request in runtime_validation_change_control_requests if request["status"] == "pending_review"
        ]
        rejected_change_control_requests = [
            request for request in runtime_validation_change_control_requests if request["status"] == "rejected"
        ]

        blockers: list[str] = []
        warnings: list[str] = []
        if not bool(database_status["ready"]):
            blockers.append("database_not_ready")
        if not bool(database_status["writable"]):
            blockers.append("database_not_writable")
        if running_jobs > 0:
            blockers.append("running_jobs_present")
        if bool(maintenance_status["active"]):
            warnings.append("maintenance_mode_already_active")
        if queued_jobs > 0:
            warnings.append("queued_jobs_present")
        if int(database_status["pending_migration_count"]) > 0:
            warnings.append("schema_migration_pending")
        if self.worker_mode == "external" and active_workers == 0:
            warnings.append("no_active_external_workers")
        if self.worker_mode == "embedded":
            warnings.append("embedded_worker_mode")
        if runtime_validation.status != "passed":
            runtime_warning_code = f"runtime_validation_{runtime_validation.status}"
            if self.settings.maintenance_runtime_validation_required:
                blockers.append(runtime_warning_code)
            else:
                warnings.append(runtime_warning_code)
        if live_workload_target_validation.status != "passed":
            target_warning_code = f"live_workload_target_validation_{live_workload_target_validation.status}"
            if self.settings.maintenance_live_workload_target_validation_required:
                blockers.append(target_warning_code)
            else:
                warnings.append(target_warning_code)
        if live_workload_proof_validation.status != "passed":
            live_workload_warning_code = (
                f"live_workload_proof_validation_{live_workload_proof_validation.status}"
            )
            if self.settings.maintenance_live_workload_proof_required:
                blockers.append(live_workload_warning_code)
            else:
                warnings.append(live_workload_warning_code)
        if backup_validation.status != "passed":
            backup_warning_code = f"backup_validation_{backup_validation.status}"
            if self.settings.maintenance_backup_validation_required:
                blockers.append(backup_warning_code)
            else:
                warnings.append(backup_warning_code)
        if backup_export_validation.status != "passed":
            backup_export_warning_code = f"backup_export_validation_{backup_export_validation.status}"
            if self.settings.maintenance_backup_validation_required:
                blockers.append(backup_export_warning_code)
            else:
                warnings.append(backup_export_warning_code)
        if observability_export_validation.status != "passed":
            observability_warning_code = (
                f"observability_export_validation_{observability_export_validation.status}"
            )
            if self.settings.maintenance_observability_validation_required:
                blockers.append(observability_warning_code)
            else:
                warnings.append(observability_warning_code)
        if not deployment_readiness.ready:
            if self.settings.maintenance_deployment_readiness_required:
                blockers.extend(
                    code
                    for code in deployment_readiness.blockers
                    if code not in blockers
                )
            else:
                warnings.extend(
                    code
                    for code in deployment_readiness.blockers
                    if code not in warnings
                )
        if pending_change_control_requests:
            warnings.append("runtime_validation_change_control_pending")
        if rejected_change_control_requests:
            warnings.append("runtime_validation_change_control_rejected")

        return ControlPlaneMaintenancePreflight(
            generated_at=_utc_now(),
            environment_name=self.settings.environment_name,
            worker_mode=self.worker_mode,
            maintenance_mode_active=bool(maintenance_status["active"]),
            maintenance_mode_changed_at=_string_or_none(maintenance_status.get("changed_at")),
            maintenance_mode_changed_by=_string_or_none(maintenance_status.get("changed_by")),
            maintenance_mode_reason=_string_or_none(maintenance_status.get("reason")),
            database_backend=str(database_status["backend"]),
            database_url=str(database_status["url"]),
            database_path=str(database_status["path"]),
            database_ready=bool(database_status["ready"]),
            database_writable=bool(database_status["writable"]),
            database_schema_version=int(database_status["schema_version"]),
            database_expected_schema_version=int(database_status["expected_schema_version"]),
            database_schema_ready=bool(database_status["schema_ready"]),
            database_pending_migration_count=int(database_status["pending_migration_count"]),
            worker_running=worker_running,
            active_workers=active_workers,
            queued_jobs=queued_jobs,
            running_jobs=running_jobs,
            completed_jobs=completed_jobs,
            failed_jobs=failed_jobs,
            runtime_validation=runtime_validation.to_dict(),
            live_workload_target_validation=live_workload_target_validation.to_dict(),
            live_workload_proof_validation=live_workload_proof_validation.to_dict(),
            backup_validation=backup_validation.to_dict(),
            backup_export_validation=backup_export_validation.to_dict(),
            observability_export_validation=observability_export_validation.to_dict(),
            deployment_readiness=deployment_readiness.to_dict(),
            runtime_validation_change_control_requests=runtime_validation_change_control_requests,
            blockers=blockers,
            warnings=warnings,
        )

    def execute_workflow(
        self,
        *,
        output_path: str,
        changed_by: str,
        reason: str | None = None,
        allow_running_jobs: bool = False,
        disable_maintenance_on_success: bool = True,
        actor_details: dict | None = None,
    ) -> ControlPlaneMaintenanceWorkflowSummary:
        preflight = self.build_preflight()
        effective_blockers = [
            blocker
            for blocker in preflight.blockers
            if not (allow_running_jobs and blocker == "running_jobs_present")
        ]
        if effective_blockers:
            raise ValueError(
                "Control-plane maintenance workflow preflight failed: "
                + ", ".join(sorted(effective_blockers))
            )

        started_at = _utc_now()
        maintenance_before = self.job_repository.maintenance_mode_status()
        maintenance_after_enable: dict[str, Any] | None = None
        maintenance_enabled_by_workflow = False
        steps: list[str] = ["preflight_checked"]

        self.job_service.record_maintenance_event(
            event_type="maintenance_workflow_started",
            changed_by=changed_by,
            reason=reason,
            details={
                "output_path": output_path,
                "allow_running_jobs": allow_running_jobs,
                "disable_maintenance_on_success": disable_maintenance_on_success,
                "preflight": preflight.to_dict(),
            },
            actor_details=actor_details,
        )

        try:
            if not bool(maintenance_before["active"]):
                maintenance_after_enable = self.job_service.enable_maintenance_mode(
                    changed_by=changed_by,
                    reason=reason or "control-plane maintenance workflow",
                    actor_details=actor_details,
                )
                maintenance_enabled_by_workflow = True
                steps.append("maintenance_mode_enabled")
            else:
                maintenance_after_enable = dict(maintenance_before)
                steps.append("maintenance_mode_reused")

            backup = self.backup_service.export_bundle(output_path)
            self.job_service.record_maintenance_event(
                event_type="maintenance_workflow_backup_exported",
                changed_by=changed_by,
                reason=reason,
                details=backup.to_dict(),
                actor_details=actor_details,
            )
            steps.append("backup_exported")

            schema_status = self.job_repository.migrate_schema()
            self.job_service.record_maintenance_event(
                event_type="maintenance_workflow_schema_migrated",
                changed_by=changed_by,
                reason=reason,
                details=schema_status,
                actor_details=actor_details,
            )
            steps.append("schema_migrated")

            if disable_maintenance_on_success and maintenance_enabled_by_workflow:
                maintenance_final = self.job_service.disable_maintenance_mode(
                    changed_by=changed_by,
                    reason=reason or "control-plane maintenance workflow completed",
                    actor_details=actor_details,
                )
                steps.append("maintenance_mode_disabled")
            else:
                maintenance_final = self.job_repository.maintenance_mode_status()
                if maintenance_final["active"]:
                    steps.append("maintenance_mode_left_active")
                else:
                    steps.append("maintenance_mode_remained_disabled")
        except Exception as exc:
            self.job_service.record_maintenance_event(
                event_type="maintenance_workflow_failed",
                changed_by=changed_by,
                reason=reason,
                details={
                    "error": str(exc),
                    "output_path": output_path,
                    "maintenance_mode_active": bool(self.job_repository.maintenance_mode_status()["active"]),
                },
                actor_details=actor_details,
            )
            raise

        completed_at = _utc_now()
        summary = ControlPlaneMaintenanceWorkflowSummary(
            started_at=started_at,
            completed_at=completed_at,
            changed_by=changed_by,
            reason=reason,
            backup_path=backup.path,
            disable_maintenance_on_success=disable_maintenance_on_success,
            maintenance_enabled_by_workflow=maintenance_enabled_by_workflow,
            steps=steps,
            preflight=preflight,
            maintenance_before=dict(maintenance_before),
            maintenance_after_enable=None if maintenance_after_enable is None else dict(maintenance_after_enable),
            maintenance_final=dict(maintenance_final),
            backup=backup,
            schema_status=dict(schema_status),
        )
        self.job_service.record_maintenance_event(
            event_type="maintenance_workflow_completed",
            changed_by=changed_by,
            reason=reason,
            details=summary.to_dict(),
            actor_details=actor_details,
        )
        return summary


def _string_or_none(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
