from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from lsa.services.datetime_utils import parse_datetime_value


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class ControlPlaneBackupValidationSummary:
    generated_at: str
    environment_name: str
    status: str
    severity: str
    cadence_status: str
    due_soon_age_hours: float
    warning_age_hours: float
    critical_age_hours: float
    latest_rehearsal_event_id: str | None = None
    latest_rehearsal_recorded_at: str | None = None
    latest_rehearsal_changed_by: str | None = None
    latest_rehearsal_reason: str | None = None
    latest_rehearsal_status: str | None = None
    latest_checks: dict[str, bool] | None = None
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
            "latest_rehearsal_event_id": self.latest_rehearsal_event_id,
            "latest_rehearsal_recorded_at": self.latest_rehearsal_recorded_at,
            "latest_rehearsal_changed_by": self.latest_rehearsal_changed_by,
            "latest_rehearsal_reason": self.latest_rehearsal_reason,
            "latest_rehearsal_status": self.latest_rehearsal_status,
            "latest_checks": {} if self.latest_checks is None else dict(self.latest_checks),
            "age_hours": self.age_hours,
            "next_due_at": self.next_due_at,
            "due_in_hours": self.due_in_hours,
            "blockers": [] if self.blockers is None else list(self.blockers),
        }


@dataclass(slots=True)
class ControlPlaneBackupValidationService:
    job_repository: Any
    environment_name: str
    due_soon_age_hours: float
    warning_age_hours: float
    critical_age_hours: float
    now_factory: Any = _utc_now

    def build_summary(self) -> ControlPlaneBackupValidationSummary:
        now = self.now_factory()
        latest_event = self._find_latest_backup_rehearsal_event()
        if latest_event is None:
            return ControlPlaneBackupValidationSummary(
                generated_at=now.isoformat(),
                environment_name=self.environment_name,
                status="missing",
                severity="critical",
                cadence_status="missing",
                due_soon_age_hours=self.due_soon_age_hours,
                warning_age_hours=self.warning_age_hours,
                critical_age_hours=self.critical_age_hours,
                blockers=["missing_backup_rehearsal"],
            )

        details = dict(latest_event.details)
        recorded_at = parse_datetime_value(latest_event.recorded_at) or now
        age_hours = max((now - recorded_at).total_seconds() / 3600.0, 0.0)
        latest_rehearsal_status = str(details.get("status", "unknown"))
        blockers: list[str] = []
        next_due_at = (recorded_at + timedelta(hours=self.warning_age_hours)).isoformat()
        due_in_hours = max(self.warning_age_hours - age_hours, 0.0)

        if latest_rehearsal_status != "passed":
            status = "failed"
            severity = "critical"
            cadence_status = "failed"
            blockers.append("backup_rehearsal_failed")
        elif age_hours >= self.critical_age_hours:
            status = "critical"
            severity = "critical"
            cadence_status = "overdue"
            blockers.append("backup_rehearsal_stale")
        elif age_hours >= self.warning_age_hours:
            status = "warning"
            severity = "warning"
            cadence_status = "aging"
            blockers.append("backup_rehearsal_aging")
        elif age_hours >= self.due_soon_age_hours:
            status = "passed"
            severity = "none"
            cadence_status = "due_soon"
        else:
            status = "passed"
            severity = "none"
            cadence_status = "fresh"

        return ControlPlaneBackupValidationSummary(
            generated_at=now.isoformat(),
            environment_name=self.environment_name,
            status=status,
            severity=severity,
            cadence_status=cadence_status,
            due_soon_age_hours=self.due_soon_age_hours,
            warning_age_hours=self.warning_age_hours,
            critical_age_hours=self.critical_age_hours,
            latest_rehearsal_event_id=latest_event.event_id,
            latest_rehearsal_recorded_at=_optional_timestamp_str(latest_event.recorded_at),
            latest_rehearsal_changed_by=latest_event.changed_by,
            latest_rehearsal_reason=latest_event.reason,
            latest_rehearsal_status=latest_rehearsal_status,
            latest_checks=_optional_bool_map(details.get("checks")),
            age_hours=age_hours,
            next_due_at=next_due_at,
            due_in_hours=due_in_hours,
            blockers=blockers,
        )

    def _find_latest_backup_rehearsal_event(self) -> Any | None:
        for record in self.job_repository.list_control_plane_maintenance_events(limit=500):
            if record.event_type != "control_plane_backup_rehearsal_executed":
                continue
            event_environment = record.details.get("environment_name")
            if event_environment is not None and event_environment != self.environment_name:
                continue
            return record
        return None


def _optional_bool_map(value: Any) -> dict[str, bool] | None:
    if not isinstance(value, dict):
        return None
    return {str(key): bool(item) for key, item in value.items()}


def _optional_timestamp_str(value: Any) -> str | None:
    parsed = parse_datetime_value(value)
    if parsed is not None:
        return parsed.isoformat()
    if value is None:
        return None
    return str(value)
