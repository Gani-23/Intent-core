from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from lsa.services.datetime_utils import parse_datetime_value


@dataclass(slots=True)
class ControlPlaneSoakValidationEvidenceSummary:
    environment_name: str
    status: str
    latest_soak_at: str | None
    latest_soak_id: str | None
    latest_soak_event_id: str | None
    latest_soak_result: str | None
    latest_expected_backend: str | None
    latest_iterations: int | None
    latest_passed_iterations: int | None
    latest_failed_iterations: int | None
    active_soak_id: str | None
    active_current_iteration: int | None
    active_total_iterations: int | None
    active_last_iteration_status: str | None
    active_target_profile_name: str | None
    active_progress_at: str | None
    age_hours: float | None
    blockers: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment_name": self.environment_name,
            "status": self.status,
            "latest_soak_at": self.latest_soak_at,
            "latest_soak_id": self.latest_soak_id,
            "latest_soak_event_id": self.latest_soak_event_id,
            "latest_soak_result": self.latest_soak_result,
            "latest_expected_backend": self.latest_expected_backend,
            "latest_iterations": self.latest_iterations,
            "latest_passed_iterations": self.latest_passed_iterations,
            "latest_failed_iterations": self.latest_failed_iterations,
            "active_soak_id": self.active_soak_id,
            "active_current_iteration": self.active_current_iteration,
            "active_total_iterations": self.active_total_iterations,
            "active_last_iteration_status": self.active_last_iteration_status,
            "active_target_profile_name": self.active_target_profile_name,
            "active_progress_at": self.active_progress_at,
            "age_hours": self.age_hours,
            "blockers": list(self.blockers),
        }


@dataclass(slots=True)
class ControlPlaneSoakValidationEvidenceService:
    job_repository: Any
    environment_name: str
    warning_age_hours: float
    critical_age_hours: float

    def build_summary(self) -> ControlPlaneSoakValidationEvidenceSummary:
        latest = None
        latest_progress = None
        for event in self.job_repository.list_control_plane_maintenance_events(limit=200):
            details = dict(event.details or {})
            if details.get("environment_name", self.environment_name) != self.environment_name:
                continue
            if latest is None and event.event_type == "control_plane_soak_validation_executed":
                latest = event
            if latest_progress is None and event.event_type in {
                "control_plane_soak_validation_started",
                "control_plane_soak_validation_progressed",
            }:
                latest_progress = event
            if latest is not None and latest_progress is not None:
                break
        latest_progress_details = dict(latest_progress.details or {}) if latest_progress is not None else {}
        latest_completed_details = dict(latest.details or {}) if latest is not None else {}
        active_soak_id = None
        active_current_iteration = None
        active_total_iterations = None
        active_last_iteration_status = None
        active_target_profile_name = None
        active_progress_at = None
        if latest_progress is not None:
            progress_soak_id = latest_progress_details.get("soak_id")
            completed_soak_id = latest_completed_details.get("soak_id")
            if progress_soak_id and progress_soak_id != completed_soak_id:
                active_soak_id = str(progress_soak_id)
                active_current_iteration = _optional_int(latest_progress_details.get("current_iteration"))
                active_total_iterations = _optional_int(latest_progress_details.get("iterations"))
                active_last_iteration_status = _optional_str(latest_progress_details.get("last_iteration_status")) or "running"
                active_target_profile_name = _optional_str(latest_progress_details.get("target_profile_name"))
                active_progress_at = _optional_str(latest_progress_details.get("executed_at") or latest_progress.recorded_at)
        if latest is None:
            if active_soak_id is not None:
                return ControlPlaneSoakValidationEvidenceSummary(
                    environment_name=self.environment_name,
                    status="running",
                    latest_soak_at=active_progress_at,
                    latest_soak_id=active_soak_id,
                    latest_soak_event_id=latest_progress.event_id if latest_progress is not None else None,
                    latest_soak_result="running",
                    latest_expected_backend=_optional_str(latest_progress_details.get("expected_backend")),
                    latest_iterations=active_total_iterations,
                    latest_passed_iterations=_optional_int(latest_progress_details.get("passed_iterations")),
                    latest_failed_iterations=_optional_int(latest_progress_details.get("failed_iterations")),
                    active_soak_id=active_soak_id,
                    active_current_iteration=active_current_iteration,
                    active_total_iterations=active_total_iterations,
                    active_last_iteration_status=active_last_iteration_status,
                    active_target_profile_name=active_target_profile_name,
                    active_progress_at=active_progress_at,
                    age_hours=None,
                    blockers=[],
                )
            return ControlPlaneSoakValidationEvidenceSummary(
                environment_name=self.environment_name,
                status="missing",
                latest_soak_at=None,
                latest_soak_id=None,
                latest_soak_event_id=None,
                latest_soak_result=None,
                latest_expected_backend=None,
                latest_iterations=None,
                latest_passed_iterations=None,
                latest_failed_iterations=None,
                active_soak_id=None,
                active_current_iteration=None,
                active_total_iterations=None,
                active_last_iteration_status=None,
                active_target_profile_name=None,
                active_progress_at=None,
                age_hours=None,
                blockers=["No soak validation evidence exists for the active environment."],
            )
        details = latest_completed_details
        recorded_at = str(details.get("executed_at") or latest.recorded_at)
        parsed_recorded_at = parse_datetime_value(recorded_at) or datetime.now(UTC)
        age_hours = max(0.0, (datetime.now(UTC) - parsed_recorded_at).total_seconds() / 3600.0)
        latest_result = str(details.get("status") or "unknown")
        blockers: list[str] = []
        status = "passed"
        if active_soak_id is not None:
            status = "running"
        elif latest_result != "passed":
            status = "failed"
            blockers.append("Latest soak validation did not pass.")
        elif age_hours >= self.critical_age_hours:
            status = "critical"
            blockers.append("Soak validation evidence is older than the critical threshold.")
        elif age_hours >= self.warning_age_hours:
            status = "warning"
            blockers.append("Soak validation evidence is older than the warning threshold.")
        return ControlPlaneSoakValidationEvidenceSummary(
            environment_name=self.environment_name,
            status=status,
            latest_soak_at=recorded_at,
            latest_soak_id=details.get("soak_id"),
            latest_soak_event_id=latest.event_id,
            latest_soak_result=latest_result,
            latest_expected_backend=details.get("expected_backend"),
            latest_iterations=details.get("iterations"),
            latest_passed_iterations=details.get("passed_iterations"),
            latest_failed_iterations=details.get("failed_iterations"),
            active_soak_id=active_soak_id,
            active_current_iteration=active_current_iteration,
            active_total_iterations=active_total_iterations,
            active_last_iteration_status=active_last_iteration_status,
            active_target_profile_name=active_target_profile_name,
            active_progress_at=active_progress_at,
            age_hours=age_hours,
            blockers=blockers,
        )


def _optional_str(value: Any) -> str | None:
    if value in {None, ""}:
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
