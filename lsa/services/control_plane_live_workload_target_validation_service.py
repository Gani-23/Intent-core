from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from lsa.services.datetime_utils import parse_datetime_value
from lsa.services.live_workload_target_profile_service import LiveWorkloadTargetProfileService


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class ControlPlaneLiveWorkloadTargetValidationSummary:
    generated_at: str
    environment_name: str
    status: str
    severity: str
    cadence_status: str
    due_soon_age_hours: float
    target_mode: str
    target_profile: str
    approved_target_base_url: str | None
    drift_target_base_url: str | None
    timeout_seconds: float
    age_hours: float | None
    warning_age_hours: float
    critical_age_hours: float
    next_due_at: str | None
    results: dict[str, Any]
    blockers: list[str]
    latest_validation_event_id: str | None = None
    latest_validation_recorded_at: str | None = None
    latest_validation_changed_by: str | None = None
    latest_validation_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "environment_name": self.environment_name,
            "status": self.status,
            "severity": self.severity,
            "cadence_status": self.cadence_status,
            "due_soon_age_hours": self.due_soon_age_hours,
            "target_mode": self.target_mode,
            "target_profile": self.target_profile,
            "approved_target_base_url": self.approved_target_base_url,
            "drift_target_base_url": self.drift_target_base_url,
            "timeout_seconds": self.timeout_seconds,
            "age_hours": self.age_hours,
            "warning_age_hours": self.warning_age_hours,
            "critical_age_hours": self.critical_age_hours,
            "next_due_at": self.next_due_at,
            "results": dict(self.results),
            "blockers": list(self.blockers),
            "latest_validation_event_id": self.latest_validation_event_id,
            "latest_validation_recorded_at": self.latest_validation_recorded_at,
            "latest_validation_changed_by": self.latest_validation_changed_by,
            "latest_validation_reason": self.latest_validation_reason,
        }


@dataclass(slots=True)
class ControlPlaneLiveWorkloadTargetValidationService:
    settings: Any
    job_repository: Any
    job_service: Any
    live_workload_drift_proof_service: Any
    now_factory: Any = _utc_now

    def _describe_target_pair(self) -> dict[str, Any]:
        if self.live_workload_drift_proof_service is not None:
            return self.live_workload_drift_proof_service.describe_target_pair()
        approved = (getattr(self.settings, "workload_proof_approved_base_url", None) or "").strip().rstrip("/")
        drift = (getattr(self.settings, "workload_proof_drift_base_url", None) or "").strip().rstrip("/")
        profile = getattr(self.settings, "workload_proof_target_profile", "embedded")
        if approved and drift:
            return {
                "target_mode": "external",
                "target_profile": profile or "custom-external-pair",
                "approved_target_base_url": approved,
                "drift_target_base_url": drift,
            }
        resolved_profile = LiveWorkloadTargetProfileService(self.settings).resolve(profile)
        if resolved_profile is not None:
            return {
                "target_mode": "external",
                "target_profile": resolved_profile.name,
                "approved_target_base_url": resolved_profile.approved_base_url,
                "drift_target_base_url": resolved_profile.drift_base_url,
            }
        return {
            "target_mode": "embedded",
            "target_profile": "embedded",
            "approved_target_base_url": None,
            "drift_target_base_url": None,
        }

    def execute(
        self,
        *,
        changed_by: str,
        reason: str | None = None,
        timeout_seconds: float = 10.0,
        actor_details: dict | None = None,
        target_profile_name: str | None = None,
        approved_base_url: str | None = None,
        drift_base_url: str | None = None,
    ) -> ControlPlaneLiveWorkloadTargetValidationSummary:
        probe = self.live_workload_drift_proof_service.probe_target_pair(
            timeout_seconds=timeout_seconds,
            target_profile_name=target_profile_name,
            approved_base_url=approved_base_url,
            drift_base_url=drift_base_url,
        )
        summary = ControlPlaneLiveWorkloadTargetValidationSummary(
            generated_at=self.now_factory().isoformat(),
            environment_name=self.settings.environment_name,
            status=str(probe.get("status", "failed")),
            severity="none" if str(probe.get("status", "failed")) == "passed" else "critical",
            cadence_status="fresh" if str(probe.get("status", "failed")) == "passed" else "failed",
            due_soon_age_hours=self.settings.analytics_live_workload_target_validation_due_soon_age_hours,
            target_mode=str(probe.get("target_mode", "embedded")),
            target_profile=str(probe.get("target_profile", "embedded")),
            approved_target_base_url=_optional_str(probe.get("approved_target_base_url")),
            drift_target_base_url=_optional_str(probe.get("drift_target_base_url")),
            timeout_seconds=float(probe.get("timeout_seconds", timeout_seconds)),
            age_hours=0.0,
            warning_age_hours=self.settings.analytics_live_workload_target_validation_warning_age_hours,
            critical_age_hours=self.settings.analytics_live_workload_target_validation_critical_age_hours,
            next_due_at=(self.now_factory() + timedelta(hours=self.settings.analytics_live_workload_target_validation_warning_age_hours)).isoformat(),
            results=dict(probe.get("results", {})),
            blockers=[str(item) for item in probe.get("blockers", [])],
            latest_validation_changed_by=changed_by,
            latest_validation_reason=reason,
        )
        event = self.job_service.record_maintenance_event(
            event_type="live_workload_target_validation_executed",
            changed_by=changed_by,
            reason=reason,
            details=summary.to_dict(),
            actor_details=actor_details,
        )
        summary.latest_validation_event_id = event.event_id
        summary.latest_validation_recorded_at = _optional_timestamp_str(event.recorded_at)
        return summary

    def build_summary(self) -> ControlPlaneLiveWorkloadTargetValidationSummary:
        now = self.now_factory()
        latest_event = self._find_latest_target_validation_event()
        target_pair = self._describe_target_pair()
        if latest_event is None:
            return ControlPlaneLiveWorkloadTargetValidationSummary(
                generated_at=now.isoformat(),
                environment_name=self.settings.environment_name,
                status="missing",
                severity="critical",
                cadence_status="missing",
                due_soon_age_hours=self.settings.analytics_live_workload_target_validation_due_soon_age_hours,
                target_mode=str(target_pair.get("target_mode", "embedded")),
                target_profile=str(target_pair.get("target_profile", "embedded")),
                approved_target_base_url=_optional_str(target_pair.get("approved_target_base_url")),
                drift_target_base_url=_optional_str(target_pair.get("drift_target_base_url")),
                timeout_seconds=10.0,
                age_hours=None,
                warning_age_hours=self.settings.analytics_live_workload_target_validation_warning_age_hours,
                critical_age_hours=self.settings.analytics_live_workload_target_validation_critical_age_hours,
                next_due_at=None,
                results={},
                blockers=["missing_live_workload_target_validation"],
            )

        details = dict(latest_event.details)
        recorded_at = parse_datetime_value(latest_event.recorded_at) or now
        age_hours = max((now - recorded_at).total_seconds() / 3600.0, 0.0)
        next_due_at = (recorded_at + timedelta(hours=self.settings.analytics_live_workload_target_validation_warning_age_hours)).isoformat()
        status = _optional_str(details.get("status")) or "failed"
        severity = "none"
        cadence_status = "fresh"
        blockers = [str(item) for item in details.get("blockers", [])]
        if status != "passed":
            severity = "critical"
            cadence_status = "failed"
        elif age_hours >= self.settings.analytics_live_workload_target_validation_critical_age_hours:
            status = "critical"
            severity = "critical"
            cadence_status = "overdue"
            blockers = list(blockers) + ["live_workload_target_validation_stale"]
        elif age_hours >= self.settings.analytics_live_workload_target_validation_warning_age_hours:
            status = "warning"
            severity = "warning"
            cadence_status = "aging"
            blockers = list(blockers) + ["live_workload_target_validation_aging"]
        elif age_hours >= self.settings.analytics_live_workload_target_validation_due_soon_age_hours:
            status = "passed"
            severity = "none"
            cadence_status = "due_soon"
        return ControlPlaneLiveWorkloadTargetValidationSummary(
            generated_at=now.isoformat(),
            environment_name=self.settings.environment_name,
            status=status,
            severity=severity,
            cadence_status=cadence_status,
            due_soon_age_hours=self.settings.analytics_live_workload_target_validation_due_soon_age_hours,
            target_mode=_optional_str(details.get("target_mode")) or str(target_pair.get("target_mode", "embedded")),
            target_profile=_optional_str(details.get("target_profile")) or str(target_pair.get("target_profile", "embedded")),
            approved_target_base_url=_optional_str(details.get("approved_target_base_url"))
            or _optional_str(target_pair.get("approved_target_base_url")),
            drift_target_base_url=_optional_str(details.get("drift_target_base_url"))
            or _optional_str(target_pair.get("drift_target_base_url")),
            timeout_seconds=float(details.get("timeout_seconds", 10.0)),
            age_hours=age_hours,
            warning_age_hours=self.settings.analytics_live_workload_target_validation_warning_age_hours,
            critical_age_hours=self.settings.analytics_live_workload_target_validation_critical_age_hours,
            next_due_at=next_due_at,
            results=dict(details.get("results", {})),
            blockers=blockers,
            latest_validation_event_id=latest_event.event_id,
            latest_validation_recorded_at=_optional_timestamp_str(latest_event.recorded_at),
            latest_validation_changed_by=latest_event.changed_by,
            latest_validation_reason=latest_event.reason,
        )

    def _find_latest_target_validation_event(self) -> Any | None:
        for record in self.job_repository.list_control_plane_maintenance_events(limit=500):
            if record.event_type != "live_workload_target_validation_executed":
                continue
            event_environment = record.details.get("environment_name")
            if event_environment is not None and event_environment != self.settings.environment_name:
                continue
            return record
        return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_timestamp_str(value: Any) -> str | None:
    parsed = parse_datetime_value(value)
    if parsed is not None:
        return parsed.isoformat()
    if value is None:
        return None
    return str(value)
