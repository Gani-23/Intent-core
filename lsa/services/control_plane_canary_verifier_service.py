from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class ControlPlaneCanaryVerifierSummary:
    verification_id: str
    executed_at: str
    changed_by: str
    reason: str | None
    environment_name: str
    target_profile_name: str
    expected_backend: str
    target_validation: dict[str, Any]
    drift_proof: dict[str, Any]
    operational_validation: dict[str, Any]
    checks: dict[str, bool]
    blockers: list[str] = field(default_factory=list)
    verdict: str = "blocked"
    recommended_action: str = ""
    maintenance_event_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "executed_at": self.executed_at,
            "changed_by": self.changed_by,
            "reason": self.reason,
            "environment_name": self.environment_name,
            "target_profile_name": self.target_profile_name,
            "expected_backend": self.expected_backend,
            "target_validation": dict(self.target_validation),
            "drift_proof": dict(self.drift_proof),
            "operational_validation": dict(self.operational_validation),
            "checks": dict(self.checks),
            "blockers": list(self.blockers),
            "verdict": self.verdict,
            "recommended_action": self.recommended_action,
            "maintenance_event_id": self.maintenance_event_id,
        }


@dataclass(slots=True)
class ControlPlaneCanaryVerifierService:
    settings: Any
    job_service: Any
    live_workload_target_validation_service: Any
    live_workload_drift_proof_service: Any
    runtime_rehearsal_service: Any
    deployment_readiness_service: Any
    now_factory: Any

    def run(
        self,
        *,
        changed_by: str,
        target_profile_name: str,
        expected_backend: str,
        reason: str | None = None,
        process_backups: bool = True,
        cleanup: bool = True,
        run_queue_validation: bool = True,
        run_workload_validation: bool = True,
        run_worker_recovery_validation: bool = True,
        queue_success_jobs: int = 2,
        queue_failure_jobs: int = 1,
        queue_delay_seconds: float = 0.0,
        run_inline_queue_worker: bool = True,
        workload_rounds: int = 3,
        workload_maintenance_pause_jobs: int = 3,
        inject_maintenance_mode_pause: bool = True,
        actor_details: dict | None = None,
    ) -> ControlPlaneCanaryVerifierSummary:
        verification_id = uuid4().hex[:12]
        executed_at = self.now_factory()

        target_validation = self.live_workload_target_validation_service.execute(
            changed_by=changed_by,
            reason=reason or "canary verification target validation",
            actor_details=actor_details,
            target_profile_name=target_profile_name,
        ).to_dict()
        drift_proof = self.live_workload_drift_proof_service.run(
            changed_by=changed_by,
            reason=reason or "canary verification drift proof",
            persist=True,
            actor_details=actor_details,
            target_profile_name=target_profile_name,
        ).to_dict()
        runtime_rehearsal = self.runtime_rehearsal_service.run(
            changed_by=changed_by,
            expected_backend=expected_backend,
            reason=reason or "canary verification operational validation",
            cleanup=cleanup,
            ignore_deployment_readiness=True,
            actor_details=actor_details,
        ).to_dict()
        deployment_readiness = self.deployment_readiness_service.evaluate().to_dict()
        operational_checks = {
            "runtime_rehearsal_passed": runtime_rehearsal.get("status") == "passed",
            "deployment_readiness_ready": bool(deployment_readiness.get("ready")),
            "cleanup_satisfied": bool(dict(runtime_rehearsal.get("smoke") or {}).get("cleanup_completed", True)),
        }
        operational_validation = {
            "status": "passed" if all(operational_checks.values()) else "failed",
            "mode": "canary_minimal",
            "process_backups": process_backups,
            "run_queue_validation": run_queue_validation,
            "run_workload_validation": run_workload_validation,
            "run_worker_recovery_validation": run_worker_recovery_validation,
            "queue_success_jobs": queue_success_jobs,
            "queue_failure_jobs": queue_failure_jobs,
            "queue_delay_seconds": queue_delay_seconds,
            "run_inline_queue_worker": run_inline_queue_worker,
            "workload_rounds": workload_rounds,
            "workload_maintenance_pause_jobs": workload_maintenance_pause_jobs,
            "inject_maintenance_mode_pause": inject_maintenance_mode_pause,
            "runtime_rehearsal": runtime_rehearsal,
            "deployment_readiness": deployment_readiness,
            "checks": operational_checks,
        }

        checks = {
            "target_validation_passed": target_validation.get("status") == "passed",
            "drift_proof_passed": bool(drift_proof.get("passed")),
            "operational_validation_passed": operational_validation.get("status") == "passed",
            "deployment_readiness_ready": bool(deployment_readiness.get("ready")),
        }
        blockers: list[str] = []
        if not checks["target_validation_passed"]:
            blockers.extend(str(item) for item in target_validation.get("blockers", []) or [])
        if not checks["drift_proof_passed"]:
            blockers.append("canary_drift_proof_failed")
        if not checks["operational_validation_passed"]:
            blockers.append("canary_operational_validation_failed")
        if not checks["deployment_readiness_ready"]:
            blockers.extend(str(item) for item in deployment_readiness.get("blockers", []) or [])

        blockers = sorted(set(blockers))
        verdict = "promote" if all(checks.values()) else "hold"
        recommended_action = (
            "Canary passed validation, drift proof, and operational validation. Promotion can proceed."
            if verdict == "promote"
            else "Hold promotion. Review blockers, refresh target routing, and re-run verification after fixes."
        )

        summary = ControlPlaneCanaryVerifierSummary(
            verification_id=verification_id,
            executed_at=executed_at,
            changed_by=changed_by,
            reason=reason,
            environment_name=self.settings.environment_name,
            target_profile_name=target_profile_name,
            expected_backend=expected_backend,
            target_validation=target_validation,
            drift_proof=drift_proof,
            operational_validation=operational_validation,
            checks=checks,
            blockers=blockers,
            verdict=verdict,
            recommended_action=recommended_action,
        )
        event = self.job_service.record_maintenance_event(
            event_type="control_plane_canary_verifier_executed",
            changed_by=changed_by,
            reason=reason,
            details=summary.to_dict(),
            actor_details=actor_details,
        )
        summary.maintenance_event_id = event.event_id
        return summary
