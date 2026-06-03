from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class ControlPlaneWorkerRecoveryValidationSummary:
    validation_id: str
    executed_at: str
    changed_by: str
    reason: str | None
    environment_name: str
    job_id: str
    simulated_worker_id: str
    processed_jobs: int
    final_job_status: str
    lease_event_types: list[str]
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
            "job_id": self.job_id,
            "simulated_worker_id": self.simulated_worker_id,
            "processed_jobs": self.processed_jobs,
            "final_job_status": self.final_job_status,
            "lease_event_types": list(self.lease_event_types),
            "checks": dict(self.checks),
            "status": self.status,
            "maintenance_event_id": self.maintenance_event_id,
        }


@dataclass(slots=True)
class ControlPlaneWorkerRecoveryValidationService:
    settings: Any
    job_service: Any
    now_factory: Any

    def run(
        self,
        *,
        changed_by: str,
        reason: str | None = None,
        actor_details: dict | None = None,
    ) -> ControlPlaneWorkerRecoveryValidationSummary:
        validation_id = uuid4().hex[:12]
        executed_at = self.now_factory()
        simulated_worker_id = f"stale-worker-{validation_id}"
        record = self.job_service.submit_validation_noop(
            {
                "label": f"worker-recovery-{validation_id}",
                "delay_seconds": 0.0,
                "should_fail": False,
            }
        )
        claimed = self.job_service.get_job(record.job_id)
        claimed.status = "running"
        claimed.started_at = datetime.now(UTC).isoformat()
        claimed.claimed_by_worker_id = simulated_worker_id
        claimed.lease_expires_at = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        self.job_service.job_repository.save(claimed)

        processed_jobs = 1 if self.job_service.process_next_job() else 0
        final_record = self.job_service.get_job(record.job_id)
        lease_event_types = [
            event.event_type
            for event in self.job_service.list_job_lease_events(record.job_id)
        ]
        checks = {
            "expired_lease_requeued": "lease_expired_requeued" in lease_event_types,
            "job_completed_after_recovery": final_record.status == "completed",
            "foreground_processed_job": processed_jobs >= 1,
        }
        status = "passed" if all(checks.values()) else "failed"
        summary = ControlPlaneWorkerRecoveryValidationSummary(
            validation_id=validation_id,
            executed_at=executed_at,
            changed_by=changed_by,
            reason=reason,
            environment_name=self.settings.environment_name,
            job_id=record.job_id,
            simulated_worker_id=simulated_worker_id,
            processed_jobs=processed_jobs,
            final_job_status=final_record.status,
            lease_event_types=lease_event_types,
            checks=checks,
            status=status,
        )
        event = self.job_service.record_maintenance_event(
            event_type="control_plane_worker_recovery_validation_executed",
            changed_by=changed_by,
            reason=reason,
            details=summary.to_dict(),
            actor_details=actor_details,
        )
        summary.maintenance_event_id = event.event_id
        return summary
