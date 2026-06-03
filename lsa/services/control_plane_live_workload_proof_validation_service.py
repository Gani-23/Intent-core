from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from lsa.services.datetime_utils import parse_datetime_value


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class ControlPlaneLiveWorkloadProofValidationSummary:
    generated_at: str
    environment_name: str
    status: str
    severity: str
    cadence_status: str
    due_soon_age_hours: float
    warning_age_hours: float
    critical_age_hours: float
    latest_proof_event_id: str | None = None
    latest_proof_recorded_at: str | None = None
    latest_proof_changed_by: str | None = None
    latest_proof_reason: str | None = None
    latest_proof_status: str | None = None
    latest_trace_path: str | None = None
    latest_target_mode: str | None = None
    latest_target_profile: str | None = None
    latest_approved_target_base_url: str | None = None
    latest_drift_target_base_url: str | None = None
    latest_snapshot_id: str | None = None
    latest_audit_id: str | None = None
    latest_alert_count: int | None = None
    latest_event_count: int | None = None
    latest_unexpected_targets: list[str] | None = None
    latest_impacted_functions: list[str] | None = None
    age_hours: float | None = None
    next_due_at: str | None = None
    due_in_hours: float | None = None
    blockers: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "environment_name": self.environment_name,
            "status": self.status,
            "severity": self.severity,
            "cadence_status": self.cadence_status,
            "due_soon_age_hours": self.due_soon_age_hours,
            "warning_age_hours": self.warning_age_hours,
            "critical_age_hours": self.critical_age_hours,
            "latest_proof_event_id": self.latest_proof_event_id,
            "latest_proof_recorded_at": self.latest_proof_recorded_at,
            "latest_proof_changed_by": self.latest_proof_changed_by,
            "latest_proof_reason": self.latest_proof_reason,
            "latest_proof_status": self.latest_proof_status,
            "latest_trace_path": self.latest_trace_path,
            "latest_target_mode": self.latest_target_mode,
            "latest_target_profile": self.latest_target_profile,
            "latest_approved_target_base_url": self.latest_approved_target_base_url,
            "latest_drift_target_base_url": self.latest_drift_target_base_url,
            "latest_snapshot_id": self.latest_snapshot_id,
            "latest_audit_id": self.latest_audit_id,
            "latest_alert_count": self.latest_alert_count,
            "latest_event_count": self.latest_event_count,
            "latest_unexpected_targets": [] if self.latest_unexpected_targets is None else list(self.latest_unexpected_targets),
            "latest_impacted_functions": [] if self.latest_impacted_functions is None else list(self.latest_impacted_functions),
            "age_hours": self.age_hours,
            "next_due_at": self.next_due_at,
            "due_in_hours": self.due_in_hours,
            "blockers": [] if self.blockers is None else list(self.blockers),
        }


@dataclass(slots=True)
class ControlPlaneLiveWorkloadProofValidationService:
    job_repository: Any
    environment_name: str
    due_soon_age_hours: float
    warning_age_hours: float
    critical_age_hours: float
    now_factory: Any = _utc_now

    def build_summary(self) -> ControlPlaneLiveWorkloadProofValidationSummary:
        now = self.now_factory()
        latest_event = self._find_latest_live_workload_proof_event()
        if latest_event is None:
            return ControlPlaneLiveWorkloadProofValidationSummary(
                generated_at=now.isoformat(),
                environment_name=self.environment_name,
                status="missing",
                severity="critical",
                cadence_status="missing",
                due_soon_age_hours=self.due_soon_age_hours,
                warning_age_hours=self.warning_age_hours,
                critical_age_hours=self.critical_age_hours,
                blockers=["missing_live_workload_drift_proof"],
            )

        details = dict(latest_event.details)
        recorded_at = parse_datetime_value(latest_event.recorded_at) or now
        age_hours = max((now - recorded_at).total_seconds() / 3600.0, 0.0)
        proof_passed = bool(details.get("passed"))
        proof_status = "passed" if proof_passed else "failed"
        blockers: list[str] = []
        next_due_at = (recorded_at + timedelta(hours=self.warning_age_hours)).isoformat()
        due_in_hours = max(self.warning_age_hours - age_hours, 0.0)

        if not proof_passed:
            status = "failed"
            severity = "critical"
            cadence_status = "failed"
            blockers.append("live_workload_drift_proof_failed")
        elif age_hours >= self.critical_age_hours:
            status = "critical"
            severity = "critical"
            cadence_status = "overdue"
            blockers.append("live_workload_drift_proof_stale")
        elif age_hours >= self.warning_age_hours:
            status = "warning"
            severity = "warning"
            cadence_status = "aging"
            blockers.append("live_workload_drift_proof_aging")
        elif age_hours >= self.due_soon_age_hours:
            status = "passed"
            severity = "none"
            cadence_status = "due_soon"
        else:
            status = "passed"
            severity = "none"
            cadence_status = "fresh"

        return ControlPlaneLiveWorkloadProofValidationSummary(
            generated_at=now.isoformat(),
            environment_name=self.environment_name,
            status=status,
            severity=severity,
            cadence_status=cadence_status,
            due_soon_age_hours=self.due_soon_age_hours,
            warning_age_hours=self.warning_age_hours,
            critical_age_hours=self.critical_age_hours,
            latest_proof_event_id=latest_event.event_id,
            latest_proof_recorded_at=_optional_timestamp_str(latest_event.recorded_at),
            latest_proof_changed_by=latest_event.changed_by,
            latest_proof_reason=latest_event.reason,
            latest_proof_status=proof_status,
            latest_trace_path=_optional_str(details.get("trace_path")),
            latest_target_mode=_optional_str(details.get("target_mode")),
            latest_target_profile=_optional_str(details.get("target_profile")),
            latest_approved_target_base_url=_optional_str(details.get("approved_target_base_url")),
            latest_drift_target_base_url=_optional_str(details.get("drift_target_base_url")),
            latest_snapshot_id=_optional_str(details.get("snapshot_id")),
            latest_audit_id=_optional_str(details.get("audit_id")),
            latest_alert_count=_optional_int(details.get("alert_count")),
            latest_event_count=_optional_int(details.get("event_count")),
            latest_unexpected_targets=_optional_str_list(details.get("unexpected_targets")),
            latest_impacted_functions=_optional_str_list(details.get("impacted_functions")),
            age_hours=age_hours,
            next_due_at=next_due_at,
            due_in_hours=due_in_hours,
            blockers=blockers,
        )

    def _find_latest_live_workload_proof_event(self) -> Any | None:
        for record in self.job_repository.list_control_plane_maintenance_events(limit=500):
            if record.event_type != "live_workload_drift_proof_executed":
                continue
            event_environment = record.details.get("environment_name")
            if event_environment is not None and event_environment != self.environment_name:
                continue
            return record
        return None


def _optional_timestamp_str(value: Any) -> str | None:
    parsed = parse_datetime_value(value)
    if parsed is not None:
        return parsed.isoformat()
    if value is None:
        return None
    return str(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_str_list(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    return [str(item) for item in value]
