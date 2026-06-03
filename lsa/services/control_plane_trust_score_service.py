from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class TrustScoreFactor:
    code: str
    label: str
    impact: int
    status: str
    summary: str
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "label": self.label,
            "impact": self.impact,
            "status": self.status,
            "summary": self.summary,
            "context": dict(self.context),
        }


@dataclass(slots=True)
class ControlPlaneTrustScoreSummary:
    generated_at: str
    environment_name: str
    score: int
    grade: str
    status: str
    factors: list[TrustScoreFactor] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "environment_name": self.environment_name,
            "score": self.score,
            "grade": self.grade,
            "status": self.status,
            "factors": [factor.to_dict() for factor in self.factors],
        }


@dataclass(slots=True)
class ControlPlaneTrustScoreService:
    settings: Any
    runtime_validation_service: Any
    live_workload_target_validation_service: Any
    live_workload_proof_validation_service: Any
    operational_validation_evidence_service: Any
    soak_validation_evidence_service: Any
    backup_validation_service: Any
    backup_operations_service: Any
    observability_export_service: Any
    deployment_readiness_service: Any
    runtime_validation_review_service: Any

    def build_summary(self) -> ControlPlaneTrustScoreSummary:
        runtime_validation = self.runtime_validation_service.build_summary().to_dict()
        target_validation = self.live_workload_target_validation_service.build_summary().to_dict()
        proof_validation = self.live_workload_proof_validation_service.build_summary().to_dict()
        operational_validation = self.operational_validation_evidence_service.build_summary().to_dict()
        soak_validation = self.soak_validation_evidence_service.build_summary().to_dict()
        backup_validation = self.backup_validation_service.build_summary().to_dict()
        backup_export_validation = self.backup_operations_service.latest_backup_export_validation().to_dict()
        observability_validation = self.observability_export_service.latest_export_validation().to_dict()
        deployment_readiness = self.deployment_readiness_service.evaluate().to_dict()
        active_reviews = self.runtime_validation_review_service.list_reviews(owner_team=None)
        active_change_controls = self.runtime_validation_review_service.list_change_control_requests(owner_team=None)

        score = 100
        factors: list[TrustScoreFactor] = []

        def apply_factor(
            *,
            code: str,
            label: str,
            impact: int,
            status: str,
            summary: str,
            context: dict[str, Any] | None = None,
        ) -> None:
            nonlocal score
            score = max(0, score - impact)
            factors.append(
                TrustScoreFactor(
                    code=code,
                    label=label,
                    impact=impact,
                    status=status,
                    summary=summary,
                    context=context or {},
                )
            )

        self._apply_validation_factor(
            payload=runtime_validation,
            label="Runtime validation",
            code_prefix="runtime_validation",
            factors=factors,
            apply_factor=apply_factor,
        )
        self._apply_validation_factor(
            payload=target_validation,
            label="Target validation",
            code_prefix="live_workload_target_validation",
            factors=factors,
            apply_factor=apply_factor,
        )
        self._apply_validation_factor(
            payload=proof_validation,
            label="Live workload proof",
            code_prefix="live_workload_proof_validation",
            factors=factors,
            apply_factor=apply_factor,
        )
        self._apply_simple_status_factor(
            payload=operational_validation,
            label="Operational validation",
            code_prefix="operational_validation",
            apply_factor=apply_factor,
        )
        self._apply_simple_status_factor(
            payload=backup_validation,
            label="Backup validation",
            code_prefix="backup_validation",
            apply_factor=apply_factor,
        )
        self._apply_simple_status_factor(
            payload=backup_export_validation,
            label="Backup export validation",
            code_prefix="backup_export_validation",
            apply_factor=apply_factor,
        )
        self._apply_simple_status_factor(
            payload=observability_validation,
            label="Observability export validation",
            code_prefix="observability_export_validation",
            apply_factor=apply_factor,
        )

        soak_status = str(soak_validation.get("status") or "missing").lower()
        if soak_status == "passed":
            factors.append(
                TrustScoreFactor(
                    code="soak_validation_passed",
                    label="Soak validation",
                    impact=0,
                    status="passed",
                    summary="Endurance proof completed successfully for the active environment.",
                    context={
                        "iterations": soak_validation.get("latest_iterations"),
                        "passed_iterations": soak_validation.get("latest_passed_iterations"),
                        "failed_iterations": soak_validation.get("latest_failed_iterations"),
                    },
                )
            )
        elif soak_status == "running":
            factors.append(
                TrustScoreFactor(
                    code="soak_validation_running",
                    label="Soak validation",
                    impact=0,
                    status="running",
                    summary="A long-running soak validation is currently in progress.",
                    context={
                        "current_iteration": soak_validation.get("active_current_iteration"),
                        "total_iterations": soak_validation.get("active_total_iterations"),
                        "target_profile_name": soak_validation.get("active_target_profile_name"),
                    },
                )
            )
        elif soak_status != "passed":
            impact = 12 if soak_status == "missing" else 20
            apply_factor(
                code=f"soak_validation_{soak_status}",
                label="Soak validation",
                impact=impact,
                status=soak_status,
                summary="Endurance proof is not in a passing state.",
                context={"blockers": list(soak_validation.get("blockers", []))},
            )

        if not bool(deployment_readiness.get("ready")):
            blockers = list(deployment_readiness.get("blockers", []))
            apply_factor(
                code="deployment_readiness_blocked",
                label="Deployment readiness",
                impact=18,
                status="blocked",
                summary="Deployment readiness is currently blocked by control-plane evidence or policy.",
                context={"blockers": blockers},
            )

        active_review_count = len([item for item in active_reviews if getattr(item, "status", "") != "resolved"])
        if active_review_count > 0:
            apply_factor(
                code="runtime_validation_review_backlog",
                label="Runtime review backlog",
                impact=min(10, active_review_count * 2),
                status="degraded",
                summary="Runtime-proof reviews remain open and reduce operator confidence.",
                context={"active_review_count": active_review_count},
            )

        blocking_change_controls = len(
            [item for item in active_change_controls if getattr(item, "status", "") in {"pending_review", "rejected"}]
        )
        if blocking_change_controls > 0:
            apply_factor(
                code="runtime_validation_change_control_backlog",
                label="Change-control backlog",
                impact=min(14, blocking_change_controls * 3),
                status="degraded",
                summary="Change-control debt is still open against runtime-proof policy.",
                context={"blocking_change_control_count": blocking_change_controls},
            )

        score = max(0, min(100, score))
        grade = self._grade(score)
        status = self._status(score)
        return ControlPlaneTrustScoreSummary(
            generated_at=_utc_now(),
            environment_name=self.settings.environment_name,
            score=score,
            grade=grade,
            status=status,
            factors=factors,
        )

    def _apply_validation_factor(
        self,
        *,
        payload: dict[str, Any],
        label: str,
        code_prefix: str,
        factors: list[TrustScoreFactor],
        apply_factor: Any,
    ) -> None:
        status = str(payload.get("status") or "missing").lower()
        cadence_status = str(payload.get("cadence_status") or status).lower()
        blockers = list(payload.get("blockers", []))
        if status == "passed" and cadence_status == "fresh":
            return
        if status == "passed" and cadence_status in {"due_soon", "aging", "warning"}:
            impact = 4 if cadence_status == "due_soon" else 8
            apply_factor(
                code=f"{code_prefix}_{cadence_status}",
                label=label,
                impact=impact,
                status=cadence_status,
                summary=f"{label} evidence is aging and should be refreshed soon.",
                context={"blockers": blockers},
            )
            return
        impact_map = {"missing": 16, "failed": 22, "critical": 18, "warning": 10}
        apply_factor(
            code=f"{code_prefix}_{status}",
            label=label,
            impact=impact_map.get(status, 12),
            status=status,
            summary=f"{label} is not currently in a trusted passing state.",
            context={"blockers": blockers},
        )

    def _apply_simple_status_factor(
        self,
        *,
        payload: dict[str, Any],
        label: str,
        code_prefix: str,
        apply_factor: Any,
    ) -> None:
        status = str(payload.get("status") or "missing").lower()
        if status == "passed":
            return
        impact_map = {"missing": 10, "warning": 6, "critical": 12, "failed": 16}
        apply_factor(
            code=f"{code_prefix}_{status}",
            label=label,
            impact=impact_map.get(status, 8),
            status=status,
            summary=f"{label} is not currently passing.",
            context={"blockers": list(payload.get("blockers", []))},
        )

    def _grade(self, score: int) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"

    def _status(self, score: int) -> str:
        if score >= 90:
            return "trusted"
        if score >= 75:
            return "stable"
        if score >= 60:
            return "watch"
        return "risky"
