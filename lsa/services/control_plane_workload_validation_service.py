from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class ControlPlaneWorkloadValidationSummary:
    validation_id: str
    executed_at: str
    changed_by: str
    reason: str | None
    environment_name: str
    rounds: int
    queue_success_jobs: int
    queue_failure_jobs: int
    queue_delay_seconds: float
    inject_maintenance_mode_pause: bool
    maintenance_pause_jobs: int
    queue_rounds: list[dict[str, Any]]
    maintenance_pause: dict[str, Any] | None
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
            "rounds": self.rounds,
            "queue_success_jobs": self.queue_success_jobs,
            "queue_failure_jobs": self.queue_failure_jobs,
            "queue_delay_seconds": self.queue_delay_seconds,
            "inject_maintenance_mode_pause": self.inject_maintenance_mode_pause,
            "maintenance_pause_jobs": self.maintenance_pause_jobs,
            "queue_rounds": [dict(item) for item in self.queue_rounds],
            "maintenance_pause": None if self.maintenance_pause is None else dict(self.maintenance_pause),
            "checks": dict(self.checks),
            "status": self.status,
            "maintenance_event_id": self.maintenance_event_id,
        }


@dataclass(slots=True)
class ControlPlaneWorkloadValidationService:
    settings: Any
    job_service: Any
    queue_validation_service: Any
    now_factory: Any

    def run(
        self,
        *,
        changed_by: str,
        reason: str | None = None,
        rounds: int = 3,
        queue_success_jobs: int = 5,
        queue_failure_jobs: int = 1,
        queue_delay_seconds: float = 0.0,
        inject_maintenance_mode_pause: bool = True,
        maintenance_pause_jobs: int = 3,
        run_inline_queue_worker: bool = True,
        actor_details: dict | None = None,
    ) -> ControlPlaneWorkloadValidationSummary:
        validation_id = uuid4().hex[:12]
        executed_at = self.now_factory()
        queue_rounds: list[dict[str, Any]] = []
        for round_index in range(max(rounds, 0)):
            round_summary = self.queue_validation_service.run(
                changed_by=changed_by,
                reason=f"{reason or 'workload validation'} round {round_index + 1}",
                success_jobs=queue_success_jobs,
                failure_jobs=queue_failure_jobs,
                delay_seconds=queue_delay_seconds,
                run_inline_worker=run_inline_queue_worker,
                actor_details=actor_details,
            )
            queue_rounds.append(round_summary.to_dict())

        maintenance_pause: dict[str, Any] | None = None
        if inject_maintenance_mode_pause:
            self.job_service.enable_maintenance_mode(
                changed_by=changed_by,
                reason=reason or "workload validation maintenance pause",
                actor_details=actor_details,
            )
            pause_job_ids: list[str] = []
            try:
                for index in range(max(maintenance_pause_jobs, 0)):
                    record = self.job_service.submit_validation_noop(
                        {
                            "label": f"maintenance-pause-{validation_id}-{index}",
                            "delay_seconds": queue_delay_seconds,
                            "should_fail": False,
                        }
                    )
                    pause_job_ids.append(record.job_id)
                processed_during_pause = self.job_service.run_foreground(
                    max_jobs=len(pause_job_ids),
                    idle_timeout_seconds=0.5,
                )
                queued_during_pause = sum(
                    1
                    for job_id in pause_job_ids
                    if self.job_service.get_job(job_id).status == "queued"
                )
            finally:
                self.job_service.disable_maintenance_mode(
                    changed_by=changed_by,
                    reason=reason or "workload validation maintenance recovery",
                    actor_details=actor_details,
                )
            processed_after_resume = self.job_service.run_foreground(
                max_jobs=len(pause_job_ids),
                idle_timeout_seconds=max(2.0, (queue_delay_seconds + 0.1) * max(len(pause_job_ids), 1)),
            )
            completed_after_resume = sum(
                1
                for job_id in pause_job_ids
                if self.job_service.get_job(job_id).status == "completed"
            )
            maintenance_pause = {
                "job_ids": list(pause_job_ids),
                "processed_during_pause": processed_during_pause,
                "queued_during_pause": queued_during_pause,
                "processed_after_resume": processed_after_resume,
                "completed_after_resume": completed_after_resume,
                "checks": {
                    "jobs_stayed_queued_during_pause": queued_during_pause == len(pause_job_ids),
                    "no_jobs_processed_during_pause": processed_during_pause == 0,
                    "jobs_recovered_after_resume": completed_after_resume == len(pause_job_ids),
                },
            }

        queue_rounds_passed = all(item.get("status") == "passed" for item in queue_rounds)
        maintenance_pause_passed = True
        if maintenance_pause is not None:
            maintenance_pause_passed = all(bool(value) for value in maintenance_pause.get("checks", {}).values())
        checks = {
            "queue_rounds_passed": queue_rounds_passed,
            "maintenance_pause_passed": maintenance_pause_passed,
        }
        status = "passed" if all(checks.values()) else "failed"
        summary = ControlPlaneWorkloadValidationSummary(
            validation_id=validation_id,
            executed_at=executed_at,
            changed_by=changed_by,
            reason=reason,
            environment_name=self.settings.environment_name,
            rounds=rounds,
            queue_success_jobs=queue_success_jobs,
            queue_failure_jobs=queue_failure_jobs,
            queue_delay_seconds=queue_delay_seconds,
            inject_maintenance_mode_pause=inject_maintenance_mode_pause,
            maintenance_pause_jobs=maintenance_pause_jobs,
            queue_rounds=queue_rounds,
            maintenance_pause=maintenance_pause,
            checks=checks,
            status=status,
        )
        event = self.job_service.record_maintenance_event(
            event_type="control_plane_workload_validation_executed",
            changed_by=changed_by,
            reason=reason,
            details=summary.to_dict(),
            actor_details=actor_details,
        )
        summary.maintenance_event_id = event.event_id
        return summary
