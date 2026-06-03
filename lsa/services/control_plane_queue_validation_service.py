from __future__ import annotations

from dataclasses import dataclass
from time import sleep
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class ControlPlaneQueueValidationSummary:
    validation_id: str
    executed_at: str
    changed_by: str
    reason: str | None
    environment_name: str
    submitted_jobs: int
    expected_successes: int
    expected_failures: int
    processed_jobs: int
    completed_jobs: int
    failed_jobs: int
    checks: dict[str, bool]
    status: str
    job_ids: list[str]
    maintenance_event_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "executed_at": self.executed_at,
            "changed_by": self.changed_by,
            "reason": self.reason,
            "environment_name": self.environment_name,
            "submitted_jobs": self.submitted_jobs,
            "expected_successes": self.expected_successes,
            "expected_failures": self.expected_failures,
            "processed_jobs": self.processed_jobs,
            "completed_jobs": self.completed_jobs,
            "failed_jobs": self.failed_jobs,
            "checks": dict(self.checks),
            "status": self.status,
            "job_ids": list(self.job_ids),
            "maintenance_event_id": self.maintenance_event_id,
        }


@dataclass(slots=True)
class ControlPlaneQueueValidationService:
    settings: Any
    job_service: Any
    now_factory: Any

    def run(
        self,
        *,
        changed_by: str,
        reason: str | None = None,
        success_jobs: int = 2,
        failure_jobs: int = 1,
        delay_seconds: float = 0.0,
        run_inline_worker: bool = True,
        actor_details: dict | None = None,
    ) -> ControlPlaneQueueValidationSummary:
        validation_id = uuid4().hex[:12]
        executed_at = self.now_factory()
        job_ids: list[str] = []
        for index in range(success_jobs):
            record = self.job_service.submit_validation_noop(
                {
                    "label": f"queue-validation-success-{validation_id}-{index}",
                    "delay_seconds": delay_seconds,
                    "should_fail": False,
                }
            )
            job_ids.append(record.job_id)
        for index in range(failure_jobs):
            record = self.job_service.submit_validation_noop(
                {
                    "label": f"queue-validation-failure-{validation_id}-{index}",
                    "delay_seconds": delay_seconds,
                    "should_fail": True,
                    "failure_message": "intentional queue validation failure",
                }
            )
            job_ids.append(record.job_id)

        processed_jobs = 0
        if run_inline_worker:
            processed_jobs = self.job_service.run_foreground(
                max_jobs=len(job_ids),
                idle_timeout_seconds=max(2.0, (delay_seconds + 0.1) * len(job_ids)),
            )
        else:
            deadline = 50
            while deadline > 0:
                states = [self.job_service.job_repository.get(job_id).status for job_id in job_ids]
                if all(state in {"completed", "failed"} for state in states):
                    break
                sleep(0.1)
                deadline -= 1

        completed_jobs = 0
        failed_jobs = 0
        for job_id in job_ids:
            record = self.job_service.job_repository.get(job_id)
            if record.status == "completed":
                completed_jobs += 1
            elif record.status == "failed":
                failed_jobs += 1

        terminal_jobs = completed_jobs + failed_jobs
        checks = {
            "success_jobs_completed": completed_jobs == success_jobs,
            "failure_jobs_failed": failed_jobs == failure_jobs,
            "processed_jobs_sufficient": (
                processed_jobs >= len(job_ids) or terminal_jobs >= len(job_ids)
            )
            if run_inline_worker
            else True,
        }
        status = "passed" if all(checks.values()) else "failed"
        summary = ControlPlaneQueueValidationSummary(
            validation_id=validation_id,
            executed_at=executed_at,
            changed_by=changed_by,
            reason=reason,
            environment_name=self.settings.environment_name,
            submitted_jobs=len(job_ids),
            expected_successes=success_jobs,
            expected_failures=failure_jobs,
            processed_jobs=processed_jobs,
            completed_jobs=completed_jobs,
            failed_jobs=failed_jobs,
            checks=checks,
            status=status,
            job_ids=job_ids,
        )
        event = self.job_service.record_maintenance_event(
            event_type="control_plane_queue_validation_executed",
            changed_by=changed_by,
            reason=reason,
            details=summary.to_dict(),
            actor_details=actor_details,
        )
        summary.maintenance_event_id = event.event_id
        return summary
