from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import time
from typing import Any

from lsa.services.control_plane_backup_service import ControlPlaneBackupService, ControlPlaneBackupSummary


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class ControlPlaneBackupBundleRecord:
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
class ControlPlaneBackupExportValidationSummary:
    generated_at: str
    environment_name: str
    status: str
    severity: str
    latest_export_event_id: str | None = None
    latest_exported_at: str | None = None
    latest_export_changed_by: str | None = None
    latest_export_path: str | None = None
    age_hours: float | None = None
    warning_age_hours: float = 48.0
    critical_age_hours: float = 168.0
    blockers: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
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
class ControlPlaneScheduledBackupResult:
    processed_at: str
    environment_name: str
    exported: bool
    pruned_count: int
    reason: str | None
    backup: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "processed_at": self.processed_at,
            "environment_name": self.environment_name,
            "exported": self.exported,
            "pruned_count": self.pruned_count,
            "reason": self.reason,
            "backup": None if self.backup is None else dict(self.backup),
        }


@dataclass(slots=True)
class ControlPlaneBackupOperationsService:
    settings: Any
    backup_service: ControlPlaneBackupService
    job_repository: Any
    job_service: Any
    now_factory: Any = _utc_now

    def list_backup_bundles(self) -> list[ControlPlaneBackupBundleRecord]:
        root = self.settings.control_plane_backups_dir
        root.mkdir(parents=True, exist_ok=True)
        rows: list[ControlPlaneBackupBundleRecord] = []
        for path in sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            stat = path.stat()
            rows.append(
                ControlPlaneBackupBundleRecord(
                    path=str(path.resolve()),
                    file_name=path.name,
                    modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
                    size_bytes=stat.st_size,
                )
            )
        return rows

    def prune_backup_bundles(self) -> int:
        root = self.settings.control_plane_backups_dir
        root.mkdir(parents=True, exist_ok=True)
        cutoff = self.now_factory() - timedelta(days=self.settings.backup_bundle_retention_days)
        pruned = 0
        for path in root.glob("*.json"):
            modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            if modified_at < cutoff:
                path.unlink(missing_ok=True)
                pruned += 1
        return pruned

    def export_default_bundle(
        self,
        *,
        changed_by: str,
        reason: str | None = None,
        actor_details: dict | None = None,
    ) -> ControlPlaneBackupSummary:
        root = self.settings.control_plane_backups_dir
        root.mkdir(parents=True, exist_ok=True)
        stamp = self.now_factory().strftime("%Y%m%dT%H%M%SZ")
        output_path = root / f"{self.settings.environment_name}-control-plane-backup-{stamp}.json"
        summary = self.backup_service.export_bundle(str(output_path))
        self.job_service.record_maintenance_event(
            event_type="backup_exported",
            changed_by=changed_by,
            reason=reason,
            details=summary.to_dict(),
            actor_details=actor_details,
        )
        return summary

    def latest_backup_export_validation(self) -> ControlPlaneBackupExportValidationSummary:
        now = self.now_factory()
        latest = self._find_latest_backup_export_event()
        if latest is None:
            return ControlPlaneBackupExportValidationSummary(
                generated_at=now.isoformat(),
                environment_name=self.settings.environment_name,
                status="missing",
                severity="critical",
                warning_age_hours=self.settings.analytics_backup_export_warning_age_hours,
                critical_age_hours=self.settings.analytics_backup_export_critical_age_hours,
                blockers=["missing_backup_export"],
            )
        details = dict(latest.details)
        exported_at_raw = str(details.get("exported_at", latest.recorded_at))
        exported_at = datetime.fromisoformat(exported_at_raw)
        age_hours = max((now - exported_at).total_seconds() / 3600.0, 0.0)
        blockers: list[str] = []
        if age_hours >= self.settings.analytics_backup_export_critical_age_hours:
            status = "critical"
            severity = "critical"
            blockers.append("backup_export_stale")
        elif age_hours >= self.settings.analytics_backup_export_warning_age_hours:
            status = "warning"
            severity = "warning"
            blockers.append("backup_export_aging")
        else:
            status = "passed"
            severity = "none"
        return ControlPlaneBackupExportValidationSummary(
            generated_at=now.isoformat(),
            environment_name=self.settings.environment_name,
            status=status,
            severity=severity,
            latest_export_event_id=latest.event_id,
            latest_exported_at=exported_at_raw,
            latest_export_changed_by=latest.changed_by,
            latest_export_path=str(details.get("path", "")) or None,
            age_hours=age_hours,
            warning_age_hours=self.settings.analytics_backup_export_warning_age_hours,
            critical_age_hours=self.settings.analytics_backup_export_critical_age_hours,
            blockers=blockers,
        )

    def process_scheduled_backups(
        self,
        *,
        changed_by: str,
        reason: str | None = None,
        force: bool = False,
        actor_details: dict | None = None,
    ) -> ControlPlaneScheduledBackupResult:
        validation = self.latest_backup_export_validation()
        should_export = force or validation.status == "missing"
        if not should_export and validation.latest_exported_at is not None:
            last_exported_at = datetime.fromisoformat(validation.latest_exported_at)
            should_export = (self.now_factory() - last_exported_at).total_seconds() >= self.settings.backup_export_interval_seconds
        summary = None
        if should_export:
            summary = self.export_default_bundle(
                changed_by=changed_by,
                reason=reason or "scheduled backup export",
                actor_details=actor_details,
            )
        pruned_count = self.prune_backup_bundles()
        result = ControlPlaneScheduledBackupResult(
            processed_at=self.now_factory().isoformat(),
            environment_name=self.settings.environment_name,
            exported=summary is not None,
            pruned_count=pruned_count,
            reason=reason,
            backup=None if summary is None else summary.to_dict(),
        )
        self.job_service.record_maintenance_event(
            event_type="scheduled_backup_processed",
            changed_by=changed_by,
            reason=reason,
            details=result.to_dict(),
            actor_details=actor_details,
        )
        return result

    def _find_latest_backup_export_event(self) -> Any | None:
        for record in self.job_repository.list_control_plane_maintenance_events(limit=500):
            if record.event_type != "backup_exported":
                continue
            event_environment = record.details.get("environment_name")
            if event_environment is not None and event_environment != self.settings.environment_name:
                continue
            return record
        return None
