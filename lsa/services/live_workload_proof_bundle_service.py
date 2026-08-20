from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from lsa.services.datetime_utils import json_safe


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class LiveWorkloadProofBundleSummary:
    exported_at: str
    environment_name: str
    target_profile: str
    output_path: str
    sha256: str
    size_bytes: int
    latest_target_validation_event_id: str | None
    latest_proof_event_id: str | None
    latest_operational_validation_event_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "exported_at": self.exported_at,
            "environment_name": self.environment_name,
            "target_profile": self.target_profile,
            "output_path": self.output_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "latest_target_validation_event_id": self.latest_target_validation_event_id,
            "latest_proof_event_id": self.latest_proof_event_id,
            "latest_operational_validation_event_id": self.latest_operational_validation_event_id,
        }


@dataclass(slots=True)
class LiveWorkloadProofBundleRecord:
    path: str
    file_name: str
    modified_at: str
    size_bytes: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "file_name": self.file_name,
            "modified_at": self.modified_at,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(slots=True)
class LiveWorkloadProofBundleInspection:
    path: str
    file_name: str
    size_bytes: int
    sha256: str
    valid: bool
    exported_at: str | None
    environment_name: str | None
    organization_name: str | None
    target_profile: str | None
    latest_target_validation_event_id: str | None
    latest_proof_event_id: str | None
    latest_operational_validation_event_id: str | None
    blockers: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "file_name": self.file_name,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "valid": self.valid,
            "exported_at": self.exported_at,
            "environment_name": self.environment_name,
            "organization_name": self.organization_name,
            "target_profile": self.target_profile,
            "latest_target_validation_event_id": self.latest_target_validation_event_id,
            "latest_proof_event_id": self.latest_proof_event_id,
            "latest_operational_validation_event_id": self.latest_operational_validation_event_id,
            "blockers": list(self.blockers),
        }


@dataclass(slots=True)
class LiveWorkloadProofBundlePruneResult:
    pruned_at: str
    retention_days: int
    before_count: int
    after_count: int
    pruned_count: int
    deleted_paths: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "pruned_at": self.pruned_at,
            "retention_days": self.retention_days,
            "before_count": self.before_count,
            "after_count": self.after_count,
            "pruned_count": self.pruned_count,
            "deleted_paths": list(self.deleted_paths),
        }


@dataclass(slots=True)
class LiveWorkloadProofBundleDeleteResult:
    deleted_at: str
    path: str
    existed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "deleted_at": self.deleted_at,
            "path": self.path,
            "existed": self.existed,
        }


@dataclass(slots=True)
class LiveWorkloadProofBundleService:
    settings: Any
    job_repository: Any
    job_service: Any
    target_validation_service: Any
    proof_validation_service: Any
    operational_validation_evidence_service: Any
    target_profile_service: Any

    def export_bundle(self, *, changed_by: str, reason: str | None = None, actor_details: dict | None = None) -> LiveWorkloadProofBundleSummary:
        exported_at = _utc_now().isoformat()
        target_validation = self.target_validation_service.build_summary().to_dict()
        proof_validation = self.proof_validation_service.build_summary().to_dict()
        operational_validation = self.operational_validation_evidence_service.build_summary().to_dict()
        profiles = [profile.to_dict() for profile in self.target_profile_service.list_profiles()]
        recent_events = [
            record.to_dict()
            for record in self.job_repository.list_control_plane_maintenance_events(limit=200)
            if record.event_type in {
                "live_workload_target_validation_executed",
                "live_workload_drift_proof_executed",
                "control_plane_operational_validation_executed",
            }
        ]
        payload = {
            "exported_at": exported_at,
            "environment_name": self.settings.environment_name,
            "organization_name": self.settings.organization_name,
            "target_profile": target_validation.get("target_profile"),
            "target_validation": target_validation,
            "proof_validation": proof_validation,
            "operational_validation": operational_validation,
            "available_target_profiles": profiles,
            "recent_maintenance_events": recent_events,
        }
        self.settings.live_workload_proof_exports_dir.mkdir(parents=True, exist_ok=True)
        file_name = (
            f"{self.settings.organization_name}-{self.settings.environment_name}-"
            f"live-workload-proof-{exported_at.replace(':', '').replace('-', '')}.json"
        )
        output_path = self.settings.live_workload_proof_exports_dir / file_name
        output_path.write_text(json.dumps(json_safe(payload), indent=2, sort_keys=True), encoding="utf-8")
        sha256 = self._sha256_file(output_path)
        size_bytes = output_path.stat().st_size
        self.job_service.record_maintenance_event(
            event_type="live_workload_proof_bundle_exported",
            changed_by=changed_by,
            reason=reason,
            details={
                "environment_name": self.settings.environment_name,
                "organization_name": self.settings.organization_name,
                "output_path": str(output_path),
                "target_profile": target_validation.get("target_profile"),
                "sha256": sha256,
                "size_bytes": size_bytes,
                "latest_target_validation_event_id": target_validation.get("latest_validation_event_id"),
                "latest_proof_event_id": proof_validation.get("latest_proof_event_id"),
                "latest_operational_validation_event_id": operational_validation.get("latest_validation_event_id"),
            },
            actor_details=actor_details,
        )
        self.prune_bundles(
            changed_by=changed_by,
            reason="scheduled proof bundle retention prune",
            actor_details=actor_details,
        )
        return LiveWorkloadProofBundleSummary(
            exported_at=exported_at,
            environment_name=self.settings.environment_name,
            target_profile=str(target_validation.get("target_profile") or ""),
            output_path=str(output_path.resolve()),
            sha256=sha256,
            size_bytes=size_bytes,
            latest_target_validation_event_id=target_validation.get("latest_validation_event_id"),
            latest_proof_event_id=proof_validation.get("latest_proof_event_id"),
            latest_operational_validation_event_id=operational_validation.get("latest_validation_event_id"),
        )

    def list_bundles(self) -> list[LiveWorkloadProofBundleRecord]:
        directory = self.settings.live_workload_proof_exports_dir
        directory.mkdir(parents=True, exist_ok=True)
        rows: list[LiveWorkloadProofBundleRecord] = []
        for path in sorted(directory.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            stat = path.stat()
            rows.append(
                LiveWorkloadProofBundleRecord(
                    path=str(path.resolve()),
                    file_name=path.name,
                    modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
                    size_bytes=stat.st_size,
                    sha256=self._sha256_file(path),
                )
            )
        return rows

    def inspect_bundle(self, *, path: str) -> LiveWorkloadProofBundleInspection:
        bundle_path = Path(path).resolve()
        if not bundle_path.exists():
            return LiveWorkloadProofBundleInspection(
                path=str(bundle_path),
                file_name=bundle_path.name,
                size_bytes=0,
                sha256="",
                valid=False,
                exported_at=None,
                environment_name=None,
                organization_name=None,
                target_profile=None,
                latest_target_validation_event_id=None,
                latest_proof_event_id=None,
                latest_operational_validation_event_id=None,
                blockers=["missing_bundle_file"],
            )
        try:
            raw = json.loads(bundle_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return LiveWorkloadProofBundleInspection(
                path=str(bundle_path),
                file_name=bundle_path.name,
                size_bytes=bundle_path.stat().st_size,
                sha256=self._sha256_file(bundle_path),
                valid=False,
                exported_at=None,
                environment_name=None,
                organization_name=None,
                target_profile=None,
                latest_target_validation_event_id=None,
                latest_proof_event_id=None,
                latest_operational_validation_event_id=None,
                blockers=["invalid_bundle_json"],
            )
        blockers: list[str] = []
        for key in (
            "exported_at",
            "environment_name",
            "organization_name",
            "target_profile",
            "target_validation",
            "proof_validation",
            "operational_validation",
        ):
            if key not in raw:
                blockers.append(f"missing_{key}")
        valid = not blockers
        return LiveWorkloadProofBundleInspection(
            path=str(bundle_path),
            file_name=bundle_path.name,
            size_bytes=bundle_path.stat().st_size,
            sha256=self._sha256_file(bundle_path),
            valid=valid,
            exported_at=_optional_str(raw.get("exported_at")),
            environment_name=_optional_str(raw.get("environment_name")),
            organization_name=_optional_str(raw.get("organization_name")),
            target_profile=_optional_str(raw.get("target_profile")),
            latest_target_validation_event_id=_optional_nested_str(
                raw, "target_validation", "latest_validation_event_id"
            ),
            latest_proof_event_id=_optional_nested_str(raw, "proof_validation", "latest_proof_event_id"),
            latest_operational_validation_event_id=_optional_nested_str(
                raw, "operational_validation", "latest_validation_event_id"
            ),
            blockers=blockers,
        )

    def delete_bundle(
        self,
        *,
        path: str,
        changed_by: str,
        reason: str | None = None,
        actor_details: dict | None = None,
    ) -> LiveWorkloadProofBundleDeleteResult:
        bundle_path = Path(path).resolve()
        existed = bundle_path.exists()
        if existed:
            bundle_path.unlink()
        result = LiveWorkloadProofBundleDeleteResult(
            deleted_at=_utc_now().isoformat(),
            path=str(bundle_path),
            existed=existed,
        )
        self.job_service.record_maintenance_event(
            event_type="live_workload_proof_bundle_deleted",
            changed_by=changed_by,
            reason=reason,
            details=result.to_dict(),
            actor_details=actor_details,
        )
        return result

    def prune_bundles(
        self,
        *,
        changed_by: str,
        reason: str | None = None,
        actor_details: dict | None = None,
        retention_days: int | None = None,
        record_event: bool = True,
    ) -> LiveWorkloadProofBundlePruneResult:
        directory = self.settings.live_workload_proof_exports_dir
        directory.mkdir(parents=True, exist_ok=True)
        applied_retention_days = (
            self.settings.live_workload_proof_bundle_retention_days if retention_days is None else retention_days
        )
        cutoff = _utc_now() - timedelta(days=applied_retention_days)
        records = self.list_bundles()
        deleted_paths: list[str] = []
        for record in records:
            path = Path(record.path)
            modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            if modified_at < cutoff:
                path.unlink(missing_ok=True)
                deleted_paths.append(record.path)
        result = LiveWorkloadProofBundlePruneResult(
            pruned_at=_utc_now().isoformat(),
            retention_days=applied_retention_days,
            before_count=len(records),
            after_count=max(len(records) - len(deleted_paths), 0),
            pruned_count=len(deleted_paths),
            deleted_paths=deleted_paths,
        )
        if record_event:
            self.job_service.record_maintenance_event(
                event_type="live_workload_proof_bundles_pruned",
                changed_by=changed_by,
                reason=reason,
                details=result.to_dict(),
                actor_details=actor_details,
            )
        return result

    def _sha256_file(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(65536)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_nested_str(payload: dict[str, Any], parent: str, child: str) -> str | None:
    nested = payload.get(parent)
    if not isinstance(nested, dict):
        return None
    value = nested.get(child)
    if value is None:
        return None
    return str(value)
