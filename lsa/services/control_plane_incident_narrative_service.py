from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class IncidentNarrativeTimelineEntry:
    recorded_at: str
    source_type: str
    source_id: str
    title: str
    summary: str
    severity: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "recorded_at": self.recorded_at,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "title": self.title,
            "summary": self.summary,
            "severity": self.severity,
        }


@dataclass(slots=True)
class ControlPlaneIncidentNarrativeSummary:
    generated_at: str
    environment_name: str
    headline: str
    status: str
    summary: str
    likely_causes: list[str] = field(default_factory=list)
    immediate_actions: list[str] = field(default_factory=list)
    timeline: list[IncidentNarrativeTimelineEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "environment_name": self.environment_name,
            "headline": self.headline,
            "status": self.status,
            "summary": self.summary,
            "likely_causes": list(self.likely_causes),
            "immediate_actions": list(self.immediate_actions),
            "timeline": [entry.to_dict() for entry in self.timeline],
        }


@dataclass(slots=True)
class ControlPlaneIncidentNarrativeService:
    settings: Any
    job_repository: Any
    deployment_readiness_service: Any
    trust_score_service: Any

    def build_summary(self, *, limit: int = 12) -> ControlPlaneIncidentNarrativeSummary:
        alerts = self.job_repository.list_control_plane_alerts(limit=20)
        events = self.job_repository.list_control_plane_maintenance_events(limit=50)
        readiness = self.deployment_readiness_service.evaluate().to_dict()
        trust = self.trust_score_service.build_summary().to_dict()

        timeline: list[IncidentNarrativeTimelineEntry] = []
        for alert in alerts[: min(6, len(alerts))]:
            timeline.append(
                IncidentNarrativeTimelineEntry(
                    recorded_at=str(alert.created_at),
                    source_type="alert",
                    source_id=str(alert.alert_id),
                    title=str(alert.alert_key),
                    summary=str(alert.summary),
                    severity=str(alert.severity),
                )
            )
        for event in events[: min(8, len(events))]:
            details = dict(event.details or {})
            timeline.append(
                IncidentNarrativeTimelineEntry(
                    recorded_at=str(event.recorded_at),
                    source_type="maintenance_event",
                    source_id=str(event.event_id),
                    title=str(event.event_type),
                    summary=str(event.reason or details.get("status") or "control-plane activity recorded"),
                    severity=None,
                )
            )
        timeline.sort(key=lambda item: item.recorded_at, reverse=True)
        timeline = timeline[:limit]

        blockers = list(readiness.get("blockers", []))
        likely_causes = self._likely_causes(blockers=blockers, timeline=timeline)
        immediate_actions = self._immediate_actions(blockers=blockers, trust=trust)
        status = "stable" if readiness.get("ready") and trust.get("status") in {"trusted", "stable"} else "degraded"
        if blockers:
            headline = "Deployment confidence is reduced by current control-plane blockers."
            summary = (
                "Recent control-plane evidence shows active blockers across readiness, validation, "
                "or change-control paths. The timeline below highlights the latest alerts and maintenance events."
            )
        else:
            headline = "Control plane is operating within expected proof and readiness bounds."
            summary = (
                "Recent control-plane activity is healthy. Validation, proof, and readiness evidence remain aligned."
            )
        return ControlPlaneIncidentNarrativeSummary(
            generated_at=_utc_now(),
            environment_name=self.settings.environment_name,
            headline=headline,
            status=status,
            summary=summary,
            likely_causes=likely_causes,
            immediate_actions=immediate_actions,
            timeline=timeline,
        )

    def _likely_causes(
        self,
        *,
        blockers: list[str],
        timeline: list[IncidentNarrativeTimelineEntry],
    ) -> list[str]:
        causes: list[str] = []
        if any("runtime_validation" in blocker for blocker in blockers):
            causes.append("Runtime validation evidence is stale, failed, or blocked by governance debt.")
        if any("live_workload_target_validation" in blocker for blocker in blockers):
            causes.append("Target reachability or probe behavior is reducing confidence in live workload routing.")
        if any("live_workload_proof" in blocker for blocker in blockers):
            causes.append("Drift-proof evidence is not fresh enough to fully trust current runtime behavior.")
        if any("backup" in blocker for blocker in blockers):
            causes.append("Backup or export evidence is not strong enough for a confident recovery posture.")
        if any("observability" in blocker for blocker in blockers):
            causes.append("Observability export freshness is lagging and weakens external auditability.")
        if any("change_control" in blocker for blocker in blockers):
            causes.append("Open or rejected change-control requests are blocking confident promotion.")
        if not causes and timeline:
            causes.append("Recent alerts and maintenance events should be reviewed for operator context.")
        return causes[:4]

    def _immediate_actions(self, *, blockers: list[str], trust: dict[str, Any]) -> list[str]:
        actions: list[str] = []
        if any("runtime_validation" in blocker for blocker in blockers):
            actions.append("Re-run runtime rehearsal or operational validation to refresh runtime proof.")
        if any("live_workload_target_validation" in blocker for blocker in blockers):
            actions.append("Probe the active target profile and confirm approved versus drift endpoints are reachable.")
        if any("change_control" in blocker for blocker in blockers):
            actions.append("Resolve or explicitly review pending change-control debt before promotion.")
        if any("backup" in blocker for blocker in blockers):
            actions.append("Run backup rehearsal and backup export processing before higher-risk maintenance.")
        if trust.get("status") == "risky":
            actions.append("Pause promotion decisions until trust score recovers above the risky band.")
        if not actions:
            actions.append("Continue monitoring the control plane and keep proof evidence fresh on cadence.")
        return actions[:4]
