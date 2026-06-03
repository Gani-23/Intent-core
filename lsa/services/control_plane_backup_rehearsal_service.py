from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4

from lsa.services.control_plane_backup_service import ControlPlaneBackupService
from lsa.storage.database import build_sqlite_database_url
from lsa.storage.files import AuditRepository, JobRepository, SnapshotRepository


@dataclass(slots=True)
class ControlPlaneBackupRehearsalSummary:
    rehearsal_id: str
    executed_at: str
    changed_by: str
    reason: str | None
    environment_name: str
    cleanup_requested: bool
    cleanup_completed: bool
    backup_bundle_path: str
    restore_root: str
    export_counts: dict[str, int]
    restored_counts: dict[str, int]
    export_artifact_counts: dict[str, int]
    restored_artifact_counts: dict[str, int]
    checks: dict[str, bool]
    status: str
    maintenance_event_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rehearsal_id": self.rehearsal_id,
            "executed_at": self.executed_at,
            "changed_by": self.changed_by,
            "reason": self.reason,
            "environment_name": self.environment_name,
            "cleanup_requested": self.cleanup_requested,
            "cleanup_completed": self.cleanup_completed,
            "backup_bundle_path": self.backup_bundle_path,
            "restore_root": self.restore_root,
            "export_counts": dict(self.export_counts),
            "restored_counts": dict(self.restored_counts),
            "export_artifact_counts": dict(self.export_artifact_counts),
            "restored_artifact_counts": dict(self.restored_artifact_counts),
            "checks": dict(self.checks),
            "status": self.status,
            "maintenance_event_id": self.maintenance_event_id,
        }


@dataclass(slots=True)
class ControlPlaneBackupRehearsalService:
    settings: Any
    backup_service: ControlPlaneBackupService
    job_service: Any
    now_factory: Any

    def run(
        self,
        *,
        changed_by: str,
        reason: str | None = None,
        cleanup: bool = True,
        actor_details: dict | None = None,
    ) -> ControlPlaneBackupRehearsalSummary:
        rehearsal_id = uuid4().hex[:12]
        executed_at = self.now_factory()
        temp_context = TemporaryDirectory(prefix="lsa-backup-rehearsal-")
        tmp_root = Path(temp_context.name)
        backup_bundle_path = tmp_root / "control-plane-backup.json"
        restore_root = tmp_root / "restore"
        restore_root.mkdir(parents=True, exist_ok=True)
        summary: ControlPlaneBackupRehearsalSummary | None = None

        try:
            export_summary = self.backup_service.export_bundle(str(backup_bundle_path))
            restored_counts, restored_artifact_counts = self._restore_and_verify(
                bundle_path=backup_bundle_path,
                restore_root=restore_root,
            )
            checks = {
                "backup_bundle_created": backup_bundle_path.exists(),
                "restore_database_created": (restore_root / "data" / "control_plane.db").exists(),
                "record_counts_match": restored_counts == export_summary.counts,
                "artifact_counts_match": restored_artifact_counts == export_summary.artifact_counts,
                "snapshots_restored": restored_artifact_counts.get("snapshots", 0)
                >= export_summary.artifact_counts.get("snapshots", 0),
                "reports_restored": restored_artifact_counts.get("reports", 0)
                >= export_summary.artifact_counts.get("reports", 0),
            }
            status = "passed" if all(checks.values()) else "failed"
            summary = ControlPlaneBackupRehearsalSummary(
                rehearsal_id=rehearsal_id,
                executed_at=executed_at,
                changed_by=changed_by,
                reason=reason,
                environment_name=self.settings.environment_name,
                cleanup_requested=cleanup,
                cleanup_completed=False,
                backup_bundle_path=str(backup_bundle_path.resolve()),
                restore_root=str(restore_root.resolve()),
                export_counts=dict(export_summary.counts),
                restored_counts=restored_counts,
                export_artifact_counts=dict(export_summary.artifact_counts),
                restored_artifact_counts=restored_artifact_counts,
                checks=checks,
                status=status,
            )
            if cleanup:
                temp_context.cleanup()
                summary.cleanup_completed = not tmp_root.exists()
            else:
                temp_context.cleanup = lambda: None  # type: ignore[method-assign]
            event = self.job_service.record_maintenance_event(
                event_type="control_plane_backup_rehearsal_executed",
                changed_by=changed_by,
                reason=reason,
                details=summary.to_dict(),
                actor_details=actor_details,
            )
            summary.maintenance_event_id = event.event_id
            return summary
        except Exception:
            if cleanup:
                temp_context.cleanup()
            else:
                temp_context.cleanup = lambda: None  # type: ignore[method-assign]
            raise

    def _restore_and_verify(
        self,
        *,
        bundle_path: Path,
        restore_root: Path,
    ) -> tuple[dict[str, int], dict[str, int]]:
        restore_data_dir = restore_root / "data"
        restore_settings = replace(
            self.settings,
            root_dir=restore_root,
            data_dir=restore_data_dir,
            database_path=restore_data_dir / "control_plane.db",
            database_url=build_sqlite_database_url(restore_data_dir / "control_plane.db"),
            database_backend="sqlite",
            enable_postgres_runtime=False,
            postgres_runtime_database_url=None,
            snapshots_dir=restore_data_dir / "intent_graphs",
            audits_dir=restore_data_dir / "audits",
            reports_dir=restore_data_dir / "reports",
            traces_dir=restore_data_dir / "traces",
            destination_aliases_path=restore_data_dir / "destination_aliases.json",
            control_plane_alert_sink_path=restore_data_dir / "control_plane_alerts.jsonl",
            privileged_api_audit_log_path=restore_data_dir / "privileged_api_audit.jsonl",
            runtime_validation_policy_path=restore_data_dir / "runtime_validation_policy.json",
            oncall_policy_path=restore_data_dir / "oncall_policy.json",
        )
        snapshot_repository = SnapshotRepository(restore_settings)
        audit_repository = AuditRepository(restore_settings)
        job_repository = JobRepository(restore_settings)
        restore_backup_service = ControlPlaneBackupService(
            settings=restore_settings,
            snapshot_repository=snapshot_repository,
            audit_repository=audit_repository,
            job_repository=job_repository,
        )
        restore_backup_service.import_bundle(str(bundle_path), replace_existing=True)
        restored_counts = {
            "snapshots": len(snapshot_repository.list()),
            "audits": len(audit_repository.list()),
            "jobs": len(job_repository.list()),
            "workers": len(job_repository.list_workers()),
            "worker_heartbeats": len(job_repository.list_worker_heartbeats()),
            "worker_heartbeat_rollups": len(job_repository.list_worker_heartbeat_rollups()),
            "job_lease_events": len(job_repository.list_job_lease_events()),
            "job_lease_event_rollups": len(job_repository.list_job_lease_event_rollups()),
            "control_plane_alerts": len(job_repository.list_control_plane_alerts()),
            "control_plane_maintenance_events": len(job_repository.list_control_plane_maintenance_events()),
            "control_plane_alert_silences": len(job_repository.list_control_plane_alert_silences()),
            "control_plane_oncall_schedules": len(job_repository.list_control_plane_oncall_schedules()),
            "control_plane_oncall_change_requests": len(job_repository.list_control_plane_oncall_change_requests()),
        }
        restored_artifact_counts = {
            "snapshots": sum(1 for _ in restore_settings.snapshots_dir.glob("*.json")),
            "reports": sum(1 for _ in restore_settings.reports_dir.rglob("*") if _.is_file()),
        }
        return restored_counts, restored_artifact_counts
