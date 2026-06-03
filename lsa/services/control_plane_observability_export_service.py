from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from lsa.services.datetime_utils import json_safe
from lsa.services.live_workload_target_profile_service import resolve_target_headers
from lsa.services.secret_reference_service import SecretReferenceService


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class ControlPlaneObservabilityBundleRecord:
    path: str
    file_name: str
    modified_at: str
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "file_name": self.file_name,
            "modified_at": self.modified_at,
            "size_bytes": self.size_bytes,
        }


@dataclass(slots=True)
class ControlPlaneObservabilityExportSummary:
    exported_at: str
    organization_name: str
    environment_name: str
    export_path: str
    alert_count: int
    maintenance_event_count: int
    metrics_line_count: int
    delivery_state: str = "not_configured"
    delivery_status_code: int | None = None
    delivery_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "exported_at": self.exported_at,
            "organization_name": self.organization_name,
            "environment_name": self.environment_name,
            "export_path": self.export_path,
            "alert_count": self.alert_count,
            "maintenance_event_count": self.maintenance_event_count,
            "metrics_line_count": self.metrics_line_count,
            "delivery_state": self.delivery_state,
            "delivery_status_code": self.delivery_status_code,
            "delivery_error": self.delivery_error,
        }


@dataclass(slots=True)
class ControlPlaneObservabilityExportValidationSummary:
    generated_at: str
    organization_name: str
    environment_name: str
    status: str
    severity: str
    latest_export_event_id: str | None = None
    latest_exported_at: str | None = None
    latest_export_changed_by: str | None = None
    latest_export_path: str | None = None
    age_hours: float | None = None
    warning_age_hours: float = 24.0
    critical_age_hours: float = 72.0
    blockers: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "organization_name": self.organization_name,
            "environment_name": self.environment_name,
            "status": self.status,
            "severity": self.severity,
            "latest_export_event_id": self.latest_export_event_id,
            "latest_exported_at": self.latest_exported_at,
            "latest_export_changed_by": self.latest_export_changed_by,
            "latest_export_path": self.latest_export_path,
            "age_hours": self.age_hours,
            "warning_age_hours": self.warning_age_hours,
            "critical_age_hours": self.critical_age_hours,
            "blockers": [] if self.blockers is None else list(self.blockers),
        }


@dataclass(slots=True)
class ControlPlaneObservabilityExportService:
    settings: Any
    job_service: Any
    analytics_service: Any
    metrics_service: Any
    privileged_api_audit_service: Any

    def export_snapshot(
        self,
        *,
        changed_by: str,
        reason: str | None = None,
        actor_details: dict | None = None,
    ) -> ControlPlaneObservabilityExportSummary:
        exported_at = _utc_now().isoformat()
        analytics = self.analytics_service.build_control_plane_analytics(days=1).to_dict()
        metrics_text = self.metrics_service.render_prometheus(days=1)
        alerts = [record.to_dict() for record in self.job_service.list_control_plane_alerts(limit=50)]
        maintenance_events = [record.to_dict() for record in self.job_service.list_control_plane_maintenance_events(limit=100)]
        privileged_summary = self.privileged_api_audit_service.build_summary(window_hours=24.0).to_dict()
        payload = {
            "exported_at": exported_at,
            "organization_name": self.settings.organization_name,
            "environment_name": self.settings.environment_name,
            "analytics": analytics,
            "metrics": metrics_text,
            "alerts": alerts,
            "maintenance_events": maintenance_events,
            "privileged_api_audit_summary": privileged_summary,
        }
        self.settings.control_plane_observability_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{self.settings.organization_name}-{self.settings.environment_name}-observability-{exported_at.replace(':', '').replace('-', '')}.json"
        export_path = self.settings.control_plane_observability_dir / file_name
        export_path.write_text(json.dumps(json_safe(payload), indent=2, sort_keys=True), encoding="utf-8")
        delivery_state = "not_configured"
        delivery_status_code: int | None = None
        delivery_error: str | None = None
        if self.settings.observability_export_webhook_url:
            delivery_state, delivery_status_code, delivery_error = self._deliver_snapshot(payload)
        self.job_service.record_maintenance_event(
            event_type="control_plane_observability_exported",
            changed_by=changed_by,
            reason=reason,
            details={
                "organization_name": self.settings.organization_name,
                "environment_name": self.settings.environment_name,
                "export_path": str(export_path),
                "alert_count": len(alerts),
                "maintenance_event_count": len(maintenance_events),
                "metrics_line_count": len(metrics_text.splitlines()),
                "delivery_state": delivery_state,
                "delivery_status_code": delivery_status_code,
                "delivery_error": delivery_error,
            },
            actor_details=actor_details,
        )
        return ControlPlaneObservabilityExportSummary(
            exported_at=exported_at,
            organization_name=self.settings.organization_name,
            environment_name=self.settings.environment_name,
            export_path=str(export_path),
            alert_count=len(alerts),
            maintenance_event_count=len(maintenance_events),
            metrics_line_count=len(metrics_text.splitlines()),
            delivery_state=delivery_state,
            delivery_status_code=delivery_status_code,
            delivery_error=delivery_error,
        )

    def list_exports(self) -> list[ControlPlaneObservabilityBundleRecord]:
        directory = self.settings.control_plane_observability_dir
        directory.mkdir(parents=True, exist_ok=True)
        rows: list[ControlPlaneObservabilityBundleRecord] = []
        for path in sorted(directory.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            stat = path.stat()
            rows.append(
                ControlPlaneObservabilityBundleRecord(
                    path=str(path.resolve()),
                    file_name=path.name,
                    modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
                    size_bytes=stat.st_size,
                )
            )
        return rows

    def prune_exports(self) -> int:
        directory = self.settings.control_plane_observability_dir
        directory.mkdir(parents=True, exist_ok=True)
        cutoff = _utc_now() - timedelta(days=self.settings.observability_export_retention_days)
        pruned = 0
        for path in directory.glob("*.json"):
            modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            if modified_at < cutoff:
                path.unlink(missing_ok=True)
                pruned += 1
        return pruned

    def latest_export_validation(self) -> ControlPlaneObservabilityExportValidationSummary:
        now = _utc_now()
        latest = self._find_latest_export_event()
        if latest is None:
            return ControlPlaneObservabilityExportValidationSummary(
                generated_at=now.isoformat(),
                organization_name=self.settings.organization_name,
                environment_name=self.settings.environment_name,
                status="missing",
                severity="critical",
                warning_age_hours=self.settings.analytics_observability_export_warning_age_hours,
                critical_age_hours=self.settings.analytics_observability_export_critical_age_hours,
                blockers=["missing_observability_export"],
            )
        details = dict(latest.details)
        exported_at_raw = str(details.get("exported_at", latest.recorded_at))
        exported_at = datetime.fromisoformat(exported_at_raw)
        age_hours = max((now - exported_at).total_seconds() / 3600.0, 0.0)
        blockers: list[str] = []
        if age_hours >= self.settings.analytics_observability_export_critical_age_hours:
            status = "critical"
            severity = "critical"
            blockers.append("observability_export_stale")
        elif age_hours >= self.settings.analytics_observability_export_warning_age_hours:
            status = "warning"
            severity = "warning"
            blockers.append("observability_export_aging")
        else:
            status = "passed"
            severity = "none"
        return ControlPlaneObservabilityExportValidationSummary(
            generated_at=now.isoformat(),
            organization_name=self.settings.organization_name,
            environment_name=self.settings.environment_name,
            status=status,
            severity=severity,
            latest_export_event_id=latest.event_id,
            latest_exported_at=exported_at_raw,
            latest_export_changed_by=latest.changed_by,
            latest_export_path=str(details.get("export_path", "")) or None,
            age_hours=age_hours,
            warning_age_hours=self.settings.analytics_observability_export_warning_age_hours,
            critical_age_hours=self.settings.analytics_observability_export_critical_age_hours,
            blockers=blockers,
        )

    def latest_export_path(self) -> str | None:
        files = self.list_exports()
        if not files:
            return None
        return files[0].path

    def _find_latest_export_event(self) -> Any | None:
        for record in self.job_service.list_control_plane_maintenance_events(limit=500):
            if record.event_type != "control_plane_observability_exported":
                continue
            details = dict(record.details)
            if details.get("environment_name") not in {None, self.settings.environment_name}:
                continue
            if details.get("organization_name") not in {None, self.settings.organization_name}:
                continue
            return record
        return None

    def _deliver_snapshot(self, payload: dict[str, Any]) -> tuple[str, int | None, str | None]:
        headers, missing = resolve_target_headers(
            self.settings.observability_export_webhook_headers,
            secret_lookup=SecretReferenceService(self.settings.secret_aliases_path).resolve_secret_alias,
        )
        if missing:
            return "failed", None, f"Missing webhook secret references: {', '.join(sorted(missing))}"
        request = Request(
            str(self.settings.observability_export_webhook_url),
            data=json.dumps(json_safe(payload)).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            with urlopen(request, timeout=float(self.settings.observability_export_timeout_seconds)) as response:
                return "sent", int(response.getcode()), None
        except HTTPError as exc:
            return "failed", int(exc.code), str(exc)
        except URLError as exc:
            return "failed", None, str(exc)
