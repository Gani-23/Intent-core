from __future__ import annotations

from dataclasses import dataclass
from time import monotonic, sleep
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class ControlPlaneSoakValidationIterationSummary:
    iteration: int
    executed_at: str
    duration_seconds: float
    status: str
    validation_id: str | None
    validation_event_id: str | None
    failed_checks: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "executed_at": self.executed_at,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "validation_id": self.validation_id,
            "validation_event_id": self.validation_event_id,
            "failed_checks": list(self.failed_checks),
        }


@dataclass(slots=True)
class ControlPlaneSoakValidationSummary:
    soak_id: str
    executed_at: str
    changed_by: str
    reason: str | None
    environment_name: str
    expected_backend: str
    iterations: int
    pause_seconds: float
    target_profile_name: str | None
    process_backups: bool
    passed_iterations: int
    failed_iterations: int
    results: list[ControlPlaneSoakValidationIterationSummary]
    status: str
    maintenance_event_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "soak_id": self.soak_id,
            "executed_at": self.executed_at,
            "changed_by": self.changed_by,
            "reason": self.reason,
            "environment_name": self.environment_name,
            "expected_backend": self.expected_backend,
            "iterations": self.iterations,
            "pause_seconds": self.pause_seconds,
            "target_profile_name": self.target_profile_name,
            "process_backups": self.process_backups,
            "passed_iterations": self.passed_iterations,
            "failed_iterations": self.failed_iterations,
            "results": [result.to_dict() for result in self.results],
            "status": self.status,
            "maintenance_event_id": self.maintenance_event_id,
        }


@dataclass(slots=True)
class ControlPlaneSoakValidationService:
    settings: Any
    job_service: Any
    operational_validation_service: Any
    now_factory: Any
    sleep_factory: Any = sleep

    def run(
        self,
        *,
        changed_by: str,
        expected_backend: str = "postgres",
        reason: str | None = None,
        iterations: int = 3,
        pause_seconds: float = 2.0,
        process_backups: bool = True,
        cleanup: bool = True,
        run_queue_validation: bool = True,
        run_workload_validation: bool = True,
        run_live_workload_drift_proof: bool = True,
        queue_success_jobs: int = 2,
        queue_failure_jobs: int = 1,
        queue_delay_seconds: float = 0.0,
        run_inline_queue_worker: bool = True,
        workload_rounds: int = 3,
        workload_maintenance_pause_jobs: int = 3,
        inject_maintenance_mode_pause: bool = True,
        run_worker_recovery_validation: bool = True,
        actor_details: dict | None = None,
        target_profile_name: str | None = None,
    ) -> ControlPlaneSoakValidationSummary:
        normalized_iterations = max(1, int(iterations))
        normalized_pause_seconds = max(0.0, float(pause_seconds))
        soak_id = uuid4().hex[:12]
        executed_at = self.now_factory()
        results: list[ControlPlaneSoakValidationIterationSummary] = []
        self.job_service.record_maintenance_event(
            event_type="control_plane_soak_validation_started",
            changed_by=changed_by,
            reason=reason,
            details={
                "soak_id": soak_id,
                "executed_at": executed_at,
                "changed_by": changed_by,
                "reason": reason,
                "environment_name": self.settings.environment_name,
                "expected_backend": expected_backend,
                "iterations": normalized_iterations,
                "pause_seconds": normalized_pause_seconds,
                "target_profile_name": target_profile_name,
                "process_backups": process_backups,
                "current_iteration": 0,
                "passed_iterations": 0,
                "failed_iterations": 0,
                "status": "running",
            },
            actor_details=actor_details,
        )

        for iteration in range(1, normalized_iterations + 1):
            started = monotonic()
            iteration_reason = reason or "control plane soak validation"
            if normalized_iterations > 1:
                iteration_reason = f"{iteration_reason} [{iteration}/{normalized_iterations}]"
            summary = self.operational_validation_service.run(
                changed_by=changed_by,
                expected_backend=expected_backend,
                reason=iteration_reason,
                process_backups=process_backups,
                cleanup=cleanup,
                run_queue_validation=run_queue_validation,
                run_workload_validation=run_workload_validation,
                run_live_workload_drift_proof=run_live_workload_drift_proof,
                queue_success_jobs=queue_success_jobs,
                queue_failure_jobs=queue_failure_jobs,
                queue_delay_seconds=queue_delay_seconds,
                run_inline_queue_worker=run_inline_queue_worker,
                workload_rounds=workload_rounds,
                workload_maintenance_pause_jobs=workload_maintenance_pause_jobs,
                inject_maintenance_mode_pause=inject_maintenance_mode_pause,
                run_worker_recovery_validation=run_worker_recovery_validation,
                actor_details=actor_details,
                target_profile_name=target_profile_name,
            )
            failed_checks = [name for name, passed in summary.checks.items() if not passed]
            results.append(
                ControlPlaneSoakValidationIterationSummary(
                    iteration=iteration,
                    executed_at=summary.executed_at,
                    duration_seconds=round(max(0.0, monotonic() - started), 3),
                    status=summary.status,
                    validation_id=summary.validation_id,
                    validation_event_id=summary.maintenance_event_id,
                    failed_checks=failed_checks,
                )
            )
            passed_iterations = sum(1 for result in results if result.status == "passed")
            failed_iterations = len(results) - passed_iterations
            self.job_service.record_maintenance_event(
                event_type="control_plane_soak_validation_progressed",
                changed_by=changed_by,
                reason=iteration_reason,
                details={
                    "soak_id": soak_id,
                    "executed_at": self.now_factory(),
                    "changed_by": changed_by,
                    "reason": reason,
                    "environment_name": self.settings.environment_name,
                    "expected_backend": expected_backend,
                    "iterations": normalized_iterations,
                    "pause_seconds": normalized_pause_seconds,
                    "target_profile_name": target_profile_name,
                    "process_backups": process_backups,
                    "current_iteration": iteration,
                    "passed_iterations": passed_iterations,
                    "failed_iterations": failed_iterations,
                    "last_iteration_status": summary.status,
                    "last_validation_id": summary.validation_id,
                    "last_validation_event_id": summary.maintenance_event_id,
                    "failed_checks": failed_checks,
                    "status": "running",
                },
                actor_details=actor_details,
            )
            if iteration < normalized_iterations and normalized_pause_seconds > 0:
                self.sleep_factory(normalized_pause_seconds)

        passed_iterations = sum(1 for result in results if result.status == "passed")
        failed_iterations = len(results) - passed_iterations
        status = "passed" if failed_iterations == 0 else "failed"
        soak_summary = ControlPlaneSoakValidationSummary(
            soak_id=soak_id,
            executed_at=executed_at,
            changed_by=changed_by,
            reason=reason,
            environment_name=self.settings.environment_name,
            expected_backend=expected_backend,
            iterations=normalized_iterations,
            pause_seconds=normalized_pause_seconds,
            target_profile_name=target_profile_name,
            process_backups=process_backups,
            passed_iterations=passed_iterations,
            failed_iterations=failed_iterations,
            results=results,
            status=status,
        )
        event = self.job_service.record_maintenance_event(
            event_type="control_plane_soak_validation_executed",
            changed_by=changed_by,
            reason=reason,
            details=soak_summary.to_dict(),
            actor_details=actor_details,
        )
        soak_summary.maintenance_event_id = event.event_id
        return soak_summary
