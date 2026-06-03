from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from lsa.services.datetime_utils import parse_datetime_value


@dataclass(slots=True)
class ControlPlaneOperationalValidationEvidenceSummary:
    environment_name: str
    status: str
    latest_validation_at: str | None
    latest_validation_id: str | None
    latest_validation_event_id: str | None
    latest_validation_result: str | None
    age_hours: float | None
    blockers: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment_name": self.environment_name,
            "status": self.status,
            "latest_validation_at": self.latest_validation_at,
            "latest_validation_id": self.latest_validation_id,
            "latest_validation_event_id": self.latest_validation_event_id,
            "latest_validation_result": self.latest_validation_result,
            "age_hours": self.age_hours,
            "blockers": list(self.blockers),
        }


@dataclass(slots=True)
class ControlPlaneOperationalValidationEvidenceService:
    job_repository: Any
    environment_name: str
    warning_age_hours: float
    critical_age_hours: float

    def build_summary(self) -> ControlPlaneOperationalValidationEvidenceSummary:
        latest = None
        for event in self.job_repository.list_control_plane_maintenance_events(limit=200):
            if event.event_type == "control_plane_operational_validation_executed":
                details = dict(event.details or {})
                if details.get("environment_name", self.environment_name) == self.environment_name:
                    latest = event
                    break
        if latest is None:
            return ControlPlaneOperationalValidationEvidenceSummary(
                environment_name=self.environment_name,
                status="missing",
                latest_validation_at=None,
                latest_validation_id=None,
                latest_validation_event_id=None,
                latest_validation_result=None,
                age_hours=None,
                blockers=["No operational validation evidence exists for the active environment."],
            )
        details = dict(latest.details or {})
        recorded_at = str(details.get("executed_at") or latest.recorded_at)
        parsed_recorded_at = parse_datetime_value(recorded_at) or datetime.now(UTC)
        age_hours = max(0.0, (datetime.now(UTC) - parsed_recorded_at).total_seconds() / 3600.0)
        latest_result = str(details.get("status") or "unknown")
        blockers: list[str] = []
        status = "passed"
        if latest_result != "passed":
            status = "failed"
            blockers.append("Latest operational validation did not pass.")
        elif age_hours >= self.critical_age_hours:
            status = "critical"
            blockers.append("Operational validation evidence is older than the critical threshold.")
        elif age_hours >= self.warning_age_hours:
            status = "warning"
            blockers.append("Operational validation evidence is older than the warning threshold.")
        return ControlPlaneOperationalValidationEvidenceSummary(
            environment_name=self.environment_name,
            status=status,
            latest_validation_at=recorded_at,
            latest_validation_id=details.get("validation_id"),
            latest_validation_event_id=latest.event_id,
            latest_validation_result=latest_result,
            age_hours=age_hours,
            blockers=blockers,
        )
