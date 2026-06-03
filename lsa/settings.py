from __future__ import annotations

import os
from dataclasses import dataclass
import json
from pathlib import Path

from lsa.storage.database import resolve_database_config


@dataclass(slots=True)
class WorkspaceSettings:
    root_dir: Path
    data_dir: Path
    database_path: Path
    database_url: str
    database_backend: str
    organization_name: str
    enable_postgres_runtime: bool
    postgres_runtime_database_url: str | None
    sqlite_busy_timeout_ms: int
    environment_name: str
    api_key: str | None
    api_allowed_origins: tuple[str, ...]
    api_trusted_hosts: tuple[str, ...]
    api_security_headers_enabled: bool
    oauth_enabled: bool
    oauth_validation_url: str | None
    oauth_timeout_seconds: float
    oauth_platform_app_id: str
    oauth_reports_app_id: str
    oauth_targets_app_id: str
    oauth_reviews_app_id: str
    authz_enabled: bool
    require_actor_headers: bool
    require_actor_organization_headers: bool
    authz_admin_roles: tuple[str, ...]
    authz_operator_roles: tuple[str, ...]
    authz_allowed_organizations: tuple[str, ...]
    enable_remediation_model: bool
    remediation_provider: str
    remediation_base_url: str | None
    remediation_model: str | None
    remediation_api_key: str | None
    remediation_timeout_seconds: float
    remediation_fallback_enabled: bool
    run_embedded_worker: bool
    worker_heartbeat_timeout_seconds: float
    worker_history_retention_days: int
    job_lease_history_retention_days: int
    history_prune_interval_seconds: float
    analytics_queue_warning_threshold: int
    analytics_queue_critical_threshold: int
    analytics_stale_worker_warning_threshold: int
    analytics_stale_worker_critical_threshold: int
    analytics_expired_lease_warning_threshold: int
    analytics_expired_lease_critical_threshold: int
    analytics_job_failure_rate_warning_threshold: float
    analytics_job_failure_rate_critical_threshold: float
    analytics_job_failure_rate_min_samples: int
    analytics_oncall_conflict_warning_threshold: int
    analytics_oncall_conflict_critical_threshold: int
    analytics_oncall_pending_review_warning_threshold: int
    analytics_oncall_pending_review_critical_threshold: int
    analytics_oncall_pending_review_sla_hours: float
    analytics_runtime_rehearsal_due_soon_age_hours: float
    analytics_runtime_rehearsal_warning_age_hours: float
    analytics_runtime_rehearsal_critical_age_hours: float
    analytics_live_workload_proof_due_soon_age_hours: float
    analytics_live_workload_proof_warning_age_hours: float
    analytics_live_workload_proof_critical_age_hours: float
    analytics_live_workload_target_validation_due_soon_age_hours: float
    analytics_live_workload_target_validation_warning_age_hours: float
    analytics_live_workload_target_validation_critical_age_hours: float
    workload_proof_target_profile: str
    workload_proof_approved_base_url: str | None
    workload_proof_drift_base_url: str | None
    workload_target_profiles_path: Path
    secret_aliases_path: Path
    organization_directory_path: Path
    analytics_backup_rehearsal_due_soon_age_hours: float
    analytics_backup_rehearsal_warning_age_hours: float
    analytics_backup_rehearsal_critical_age_hours: float
    analytics_backup_export_warning_age_hours: float
    analytics_backup_export_critical_age_hours: float
    analytics_observability_export_warning_age_hours: float
    analytics_observability_export_critical_age_hours: float
    analytics_operational_validation_warning_age_hours: float
    analytics_operational_validation_critical_age_hours: float
    analytics_deployment_rejected_change_control_critical_age_hours: float
    analytics_privileged_api_audit_non_ok_warning_threshold: int
    analytics_privileged_api_audit_non_ok_critical_threshold: int
    privileged_api_audit_retention_days: int
    runtime_validation_policy_path: Path
    maintenance_runtime_validation_required: bool
    maintenance_live_workload_target_validation_required: bool
    maintenance_live_workload_proof_required: bool
    maintenance_backup_validation_required: bool
    maintenance_observability_validation_required: bool
    maintenance_deployment_readiness_required: bool
    cutover_runtime_validation_required: bool
    cutover_live_workload_target_validation_required: bool
    cutover_live_workload_proof_required: bool
    cutover_backup_validation_required: bool
    cutover_observability_validation_required: bool
    runtime_rehearsal_deployment_readiness_required: bool
    job_submission_deployment_readiness_required: bool
    oncall_policy_path: Path
    oncall_approval_required_roles: tuple[str, ...]
    oncall_allow_self_approval: bool
    control_plane_alerts_enabled: bool
    control_plane_alert_window_days: int
    control_plane_alert_interval_seconds: float
    control_plane_alert_dedup_window_seconds: float
    control_plane_alert_reminder_interval_seconds: float
    control_plane_alert_escalation_interval_seconds: float
    control_plane_alert_webhook_url: str | None
    control_plane_alert_escalation_webhook_url: str | None
    control_plane_alert_sink_path: Path
    privileged_api_audit_log_path: Path
    control_plane_backups_dir: Path
    backup_export_interval_seconds: float
    backup_bundle_retention_days: int
    control_plane_observability_dir: Path
    live_workload_proof_exports_dir: Path
    live_workload_proof_bundle_retention_days: int
    observability_export_interval_seconds: float
    live_workload_target_validation_interval_seconds: float
    operational_validation_interval_seconds: float
    observability_export_retention_days: int
    observability_export_webhook_url: str | None
    observability_export_webhook_headers: dict[str, str] | None
    observability_export_timeout_seconds: float
    snapshots_dir: Path
    audits_dir: Path
    reports_dir: Path
    traces_dir: Path
    destination_aliases_path: Path
    remediation_index_path: Path


def resolve_workspace_settings(base_dir: str | Path | None = None) -> WorkspaceSettings:
    root = Path(base_dir).resolve() if base_dir else Path.cwd().resolve()
    data_dir = root / "data"
    database_config = resolve_database_config(
        root_dir=root,
        default_path=data_dir / "control_plane.db",
        raw_url=os.environ.get("LSA_DATABASE_URL"),
    )
    return WorkspaceSettings(
        root_dir=root,
        data_dir=data_dir,
        database_path=database_config.sqlite_path,
        database_url=database_config.url,
        database_backend=database_config.backend,
        organization_name=os.environ.get("LSA_ORGANIZATION_NAME", "default").strip().lower() or "default",
        enable_postgres_runtime=_env_flag("LSA_ENABLE_POSTGRES_RUNTIME", default=False),
        postgres_runtime_database_url=os.environ.get("LSA_POSTGRES_RUNTIME_DATABASE_URL"),
        sqlite_busy_timeout_ms=_env_int("LSA_SQLITE_BUSY_TIMEOUT_MS", default=5000),
        environment_name=os.environ.get("LSA_ENVIRONMENT_NAME", "default").strip().lower() or "default",
        api_key=os.environ.get("LSA_API_KEY"),
        api_allowed_origins=_env_csv_raw("LSA_API_ALLOWED_ORIGINS", default=()),
        api_trusted_hosts=_env_csv_raw("LSA_API_TRUSTED_HOSTS", default=()),
        api_security_headers_enabled=_env_flag("LSA_API_SECURITY_HEADERS_ENABLED", default=True),
        oauth_enabled=_env_flag("LSA_OAUTH_ENABLED", default=False),
        oauth_validation_url=os.environ.get(
            "LSA_OAUTH_VALIDATION_URL",
            "https://oauth4-0.onrender.com/api/users/licenses/validate",
        ),
        oauth_timeout_seconds=_env_float("LSA_OAUTH_TIMEOUT_SECONDS", default=5.0),
        oauth_platform_app_id=os.environ.get("LSA_OAUTH_PLATFORM_APP_ID", "lsa-platform").strip().lower()
        or "lsa-platform",
        oauth_reports_app_id=os.environ.get("LSA_OAUTH_REPORTS_APP_ID", "lsa-reports-read").strip().lower()
        or "lsa-reports-read",
        oauth_targets_app_id=os.environ.get("LSA_OAUTH_TARGETS_APP_ID", "lsa-targets-access").strip().lower()
        or "lsa-targets-access",
        oauth_reviews_app_id=os.environ.get("LSA_OAUTH_REVIEWS_APP_ID", "lsa-reviews-read").strip().lower()
        or "lsa-reviews-read",
        authz_enabled=_env_flag("LSA_AUTHZ_ENABLED", default=False),
        require_actor_headers=_env_flag("LSA_REQUIRE_ACTOR_HEADERS", default=False),
        require_actor_organization_headers=_env_flag("LSA_REQUIRE_ACTOR_ORGANIZATION_HEADERS", default=False),
        authz_admin_roles=_env_csv(
            "LSA_AUTHZ_ADMIN_ROLES",
            default=("admin",),
        ),
        authz_operator_roles=_env_csv(
            "LSA_AUTHZ_OPERATOR_ROLES",
            default=("operator", "admin"),
        ),
        authz_allowed_organizations=_env_csv(
            "LSA_AUTHZ_ALLOWED_ORGANIZATIONS",
            default=("default",),
        ),
        enable_remediation_model=_env_flag("LSA_ENABLE_REMEDIATION_MODEL", default=False),
        remediation_provider=os.environ.get("LSA_REMEDIATION_PROVIDER", "rule-based").strip().lower() or "rule-based",
        remediation_base_url=os.environ.get("LSA_REMEDIATION_BASE_URL"),
        remediation_model=os.environ.get("LSA_REMEDIATION_MODEL"),
        remediation_api_key=os.environ.get("LSA_REMEDIATION_API_KEY"),
        remediation_timeout_seconds=_env_float("LSA_REMEDIATION_TIMEOUT_SECONDS", default=30.0),
        remediation_fallback_enabled=_env_flag("LSA_REMEDIATION_FALLBACK_ENABLED", default=True),
        run_embedded_worker=_env_flag("LSA_RUN_EMBEDDED_WORKER", default=False),
        worker_heartbeat_timeout_seconds=_env_float("LSA_WORKER_HEARTBEAT_TIMEOUT_SECONDS", default=5.0),
        worker_history_retention_days=_env_int("LSA_WORKER_HISTORY_RETENTION_DAYS", default=14),
        job_lease_history_retention_days=_env_int("LSA_JOB_LEASE_HISTORY_RETENTION_DAYS", default=30),
        history_prune_interval_seconds=_env_float("LSA_HISTORY_PRUNE_INTERVAL_SECONDS", default=300.0),
        analytics_queue_warning_threshold=_env_int("LSA_ANALYTICS_QUEUE_WARNING_THRESHOLD", default=5),
        analytics_queue_critical_threshold=_env_int("LSA_ANALYTICS_QUEUE_CRITICAL_THRESHOLD", default=20),
        analytics_stale_worker_warning_threshold=_env_int("LSA_ANALYTICS_STALE_WORKER_WARNING_THRESHOLD", default=1),
        analytics_stale_worker_critical_threshold=_env_int("LSA_ANALYTICS_STALE_WORKER_CRITICAL_THRESHOLD", default=3),
        analytics_expired_lease_warning_threshold=_env_int("LSA_ANALYTICS_EXPIRED_LEASE_WARNING_THRESHOLD", default=1),
        analytics_expired_lease_critical_threshold=_env_int("LSA_ANALYTICS_EXPIRED_LEASE_CRITICAL_THRESHOLD", default=3),
        analytics_job_failure_rate_warning_threshold=_env_float(
            "LSA_ANALYTICS_JOB_FAILURE_RATE_WARNING_THRESHOLD",
            default=0.1,
        ),
        analytics_job_failure_rate_critical_threshold=_env_float(
            "LSA_ANALYTICS_JOB_FAILURE_RATE_CRITICAL_THRESHOLD",
            default=0.25,
        ),
        analytics_job_failure_rate_min_samples=_env_int("LSA_ANALYTICS_JOB_FAILURE_RATE_MIN_SAMPLES", default=3),
        analytics_oncall_conflict_warning_threshold=_env_int(
            "LSA_ANALYTICS_ONCALL_CONFLICT_WARNING_THRESHOLD",
            default=1,
        ),
        analytics_oncall_conflict_critical_threshold=_env_int(
            "LSA_ANALYTICS_ONCALL_CONFLICT_CRITICAL_THRESHOLD",
            default=3,
        ),
        analytics_oncall_pending_review_warning_threshold=_env_int(
            "LSA_ANALYTICS_ONCALL_PENDING_REVIEW_WARNING_THRESHOLD",
            default=1,
        ),
        analytics_oncall_pending_review_critical_threshold=_env_int(
            "LSA_ANALYTICS_ONCALL_PENDING_REVIEW_CRITICAL_THRESHOLD",
            default=3,
        ),
        analytics_oncall_pending_review_sla_hours=_env_float(
            "LSA_ANALYTICS_ONCALL_PENDING_REVIEW_SLA_HOURS",
            default=24.0,
        ),
        analytics_runtime_rehearsal_due_soon_age_hours=_env_float(
            "LSA_ANALYTICS_RUNTIME_REHEARSAL_DUE_SOON_AGE_HOURS",
            default=18.0,
        ),
        analytics_runtime_rehearsal_warning_age_hours=_env_float(
            "LSA_ANALYTICS_RUNTIME_REHEARSAL_WARNING_AGE_HOURS",
            default=24.0,
        ),
        analytics_runtime_rehearsal_critical_age_hours=_env_float(
            "LSA_ANALYTICS_RUNTIME_REHEARSAL_CRITICAL_AGE_HOURS",
            default=72.0,
        ),
        analytics_live_workload_proof_due_soon_age_hours=_env_float(
            "LSA_ANALYTICS_LIVE_WORKLOAD_PROOF_DUE_SOON_AGE_HOURS",
            default=24.0,
        ),
        analytics_live_workload_proof_warning_age_hours=_env_float(
            "LSA_ANALYTICS_LIVE_WORKLOAD_PROOF_WARNING_AGE_HOURS",
            default=72.0,
        ),
        analytics_live_workload_proof_critical_age_hours=_env_float(
            "LSA_ANALYTICS_LIVE_WORKLOAD_PROOF_CRITICAL_AGE_HOURS",
            default=168.0,
        ),
        analytics_live_workload_target_validation_due_soon_age_hours=_env_float(
            "LSA_ANALYTICS_LIVE_WORKLOAD_TARGET_VALIDATION_DUE_SOON_AGE_HOURS",
            default=18.0,
        ),
        analytics_live_workload_target_validation_warning_age_hours=_env_float(
            "LSA_ANALYTICS_LIVE_WORKLOAD_TARGET_VALIDATION_WARNING_AGE_HOURS",
            default=24.0,
        ),
        analytics_live_workload_target_validation_critical_age_hours=_env_float(
            "LSA_ANALYTICS_LIVE_WORKLOAD_TARGET_VALIDATION_CRITICAL_AGE_HOURS",
            default=72.0,
        ),
        workload_proof_target_profile=os.environ.get(
            "LSA_WORKLOAD_PROOF_TARGET_PROFILE",
            "embedded",
        ).strip().lower()
        or "embedded",
        workload_proof_approved_base_url=os.environ.get("LSA_WORKLOAD_PROOF_APPROVED_BASE_URL"),
        workload_proof_drift_base_url=os.environ.get("LSA_WORKLOAD_PROOF_DRIFT_BASE_URL"),
        workload_target_profiles_path=Path(
            os.environ.get(
                "LSA_WORKLOAD_TARGET_PROFILES_PATH",
                str(data_dir / "workload_target_profiles.json"),
            )
        ),
        secret_aliases_path=Path(
            os.environ.get(
                "LSA_SECRET_ALIASES_PATH",
                str(data_dir / "secret_aliases.json"),
            )
        ),
        organization_directory_path=Path(
            os.environ.get(
                "LSA_ORGANIZATION_DIRECTORY_PATH",
                str(data_dir / "organization_directory.json"),
            )
        ),
        analytics_backup_rehearsal_due_soon_age_hours=_env_float(
            "LSA_ANALYTICS_BACKUP_REHEARSAL_DUE_SOON_AGE_HOURS",
            default=72.0,
        ),
        analytics_backup_rehearsal_warning_age_hours=_env_float(
            "LSA_ANALYTICS_BACKUP_REHEARSAL_WARNING_AGE_HOURS",
            default=168.0,
        ),
        analytics_backup_rehearsal_critical_age_hours=_env_float(
            "LSA_ANALYTICS_BACKUP_REHEARSAL_CRITICAL_AGE_HOURS",
            default=336.0,
        ),
        analytics_backup_export_warning_age_hours=_env_float(
            "LSA_ANALYTICS_BACKUP_EXPORT_WARNING_AGE_HOURS",
            default=48.0,
        ),
        analytics_backup_export_critical_age_hours=_env_float(
            "LSA_ANALYTICS_BACKUP_EXPORT_CRITICAL_AGE_HOURS",
            default=168.0,
        ),
        analytics_observability_export_warning_age_hours=_env_float(
            "LSA_ANALYTICS_OBSERVABILITY_EXPORT_WARNING_AGE_HOURS",
            default=24.0,
        ),
        analytics_observability_export_critical_age_hours=_env_float(
            "LSA_ANALYTICS_OBSERVABILITY_EXPORT_CRITICAL_AGE_HOURS",
            default=72.0,
        ),
        analytics_operational_validation_warning_age_hours=_env_float(
            "LSA_ANALYTICS_OPERATIONAL_VALIDATION_WARNING_AGE_HOURS",
            default=24.0,
        ),
        analytics_operational_validation_critical_age_hours=_env_float(
            "LSA_ANALYTICS_OPERATIONAL_VALIDATION_CRITICAL_AGE_HOURS",
            default=72.0,
        ),
        analytics_deployment_rejected_change_control_critical_age_hours=_env_float(
            "LSA_ANALYTICS_DEPLOYMENT_REJECTED_CHANGE_CONTROL_CRITICAL_AGE_HOURS",
            default=24.0,
        ),
        analytics_privileged_api_audit_non_ok_warning_threshold=_env_int(
            "LSA_ANALYTICS_PRIVILEGED_API_AUDIT_NON_OK_WARNING_THRESHOLD",
            default=1,
        ),
        analytics_privileged_api_audit_non_ok_critical_threshold=_env_int(
            "LSA_ANALYTICS_PRIVILEGED_API_AUDIT_NON_OK_CRITICAL_THRESHOLD",
            default=3,
        ),
        privileged_api_audit_retention_days=_env_int(
            "LSA_PRIVILEGED_API_AUDIT_RETENTION_DAYS",
            default=30,
        ),
        runtime_validation_policy_path=Path(
            os.environ.get(
                "LSA_RUNTIME_VALIDATION_POLICY_PATH",
                str(data_dir / "runtime_validation_policy.json"),
            )
        ),
        maintenance_runtime_validation_required=_env_flag(
            "LSA_MAINTENANCE_RUNTIME_VALIDATION_REQUIRED",
            default=False,
        ),
        maintenance_live_workload_target_validation_required=_env_flag(
            "LSA_MAINTENANCE_LIVE_WORKLOAD_TARGET_VALIDATION_REQUIRED",
            default=False,
        ),
        maintenance_live_workload_proof_required=_env_flag(
            "LSA_MAINTENANCE_LIVE_WORKLOAD_PROOF_REQUIRED",
            default=False,
        ),
        maintenance_backup_validation_required=_env_flag(
            "LSA_MAINTENANCE_BACKUP_VALIDATION_REQUIRED",
            default=False,
        ),
        maintenance_observability_validation_required=_env_flag(
            "LSA_MAINTENANCE_OBSERVABILITY_VALIDATION_REQUIRED",
            default=False,
        ),
        maintenance_deployment_readiness_required=_env_flag(
            "LSA_MAINTENANCE_DEPLOYMENT_READINESS_REQUIRED",
            default=False,
        ),
        cutover_runtime_validation_required=_env_flag(
            "LSA_CUTOVER_RUNTIME_VALIDATION_REQUIRED",
            default=True,
        ),
        cutover_live_workload_target_validation_required=_env_flag(
            "LSA_CUTOVER_LIVE_WORKLOAD_TARGET_VALIDATION_REQUIRED",
            default=True,
        ),
        cutover_live_workload_proof_required=_env_flag(
            "LSA_CUTOVER_LIVE_WORKLOAD_PROOF_REQUIRED",
            default=True,
        ),
        cutover_backup_validation_required=_env_flag(
            "LSA_CUTOVER_BACKUP_VALIDATION_REQUIRED",
            default=True,
        ),
        cutover_observability_validation_required=_env_flag(
            "LSA_CUTOVER_OBSERVABILITY_VALIDATION_REQUIRED",
            default=True,
        ),
        runtime_rehearsal_deployment_readiness_required=_env_flag(
            "LSA_RUNTIME_REHEARSAL_DEPLOYMENT_READINESS_REQUIRED",
            default=False,
        ),
        job_submission_deployment_readiness_required=_env_flag(
            "LSA_JOB_SUBMISSION_DEPLOYMENT_READINESS_REQUIRED",
            default=False,
        ),
        oncall_policy_path=Path(
            os.environ.get("LSA_ONCALL_POLICY_PATH", str(data_dir / "oncall_policy.json"))
        ),
        oncall_approval_required_roles=_env_csv(
            "LSA_ONCALL_APPROVAL_REQUIRED_ROLES",
            default=("manager", "director", "admin"),
        ),
        oncall_allow_self_approval=_env_flag("LSA_ONCALL_ALLOW_SELF_APPROVAL", default=False),
        control_plane_alerts_enabled=_env_flag("LSA_CONTROL_PLANE_ALERTS_ENABLED", default=True),
        control_plane_alert_window_days=_env_int("LSA_CONTROL_PLANE_ALERT_WINDOW_DAYS", default=7),
        control_plane_alert_interval_seconds=_env_float("LSA_CONTROL_PLANE_ALERT_INTERVAL_SECONDS", default=60.0),
        control_plane_alert_dedup_window_seconds=_env_float(
            "LSA_CONTROL_PLANE_ALERT_DEDUP_WINDOW_SECONDS",
            default=300.0,
        ),
        control_plane_alert_reminder_interval_seconds=_env_float(
            "LSA_CONTROL_PLANE_ALERT_REMINDER_INTERVAL_SECONDS",
            default=900.0,
        ),
        control_plane_alert_escalation_interval_seconds=_env_float(
            "LSA_CONTROL_PLANE_ALERT_ESCALATION_INTERVAL_SECONDS",
            default=1800.0,
        ),
        control_plane_alert_webhook_url=os.environ.get("LSA_CONTROL_PLANE_ALERT_WEBHOOK_URL"),
        control_plane_alert_escalation_webhook_url=os.environ.get("LSA_CONTROL_PLANE_ALERT_ESCALATION_WEBHOOK_URL"),
        control_plane_alert_sink_path=data_dir / "control_plane_alerts.jsonl",
        privileged_api_audit_log_path=data_dir / "privileged_api_audit.jsonl",
        control_plane_backups_dir=data_dir / "control_plane_backups",
        backup_export_interval_seconds=_env_float(
            "LSA_BACKUP_EXPORT_INTERVAL_SECONDS",
            default=86400.0,
        ),
        backup_bundle_retention_days=_env_int(
            "LSA_BACKUP_BUNDLE_RETENTION_DAYS",
            default=30,
        ),
        control_plane_observability_dir=data_dir / "observability_exports",
        live_workload_proof_exports_dir=data_dir / "live_workload_proof_exports",
        live_workload_proof_bundle_retention_days=_env_int(
            "LSA_LIVE_WORKLOAD_PROOF_BUNDLE_RETENTION_DAYS",
            default=30,
        ),
        observability_export_interval_seconds=_env_float(
            "LSA_OBSERVABILITY_EXPORT_INTERVAL_SECONDS",
            default=900.0,
        ),
        live_workload_target_validation_interval_seconds=_env_float(
            "LSA_LIVE_WORKLOAD_TARGET_VALIDATION_INTERVAL_SECONDS",
            default=21600.0,
        ),
        operational_validation_interval_seconds=_env_float(
            "LSA_OPERATIONAL_VALIDATION_INTERVAL_SECONDS",
            default=14400.0,
        ),
        observability_export_retention_days=_env_int(
            "LSA_OBSERVABILITY_EXPORT_RETENTION_DAYS",
            default=14,
        ),
        observability_export_webhook_url=os.environ.get("LSA_OBSERVABILITY_EXPORT_WEBHOOK_URL"),
        observability_export_webhook_headers=_env_json_dict("LSA_OBSERVABILITY_EXPORT_WEBHOOK_HEADERS"),
        observability_export_timeout_seconds=_env_float(
            "LSA_OBSERVABILITY_EXPORT_TIMEOUT_SECONDS",
            default=15.0,
        ),
        snapshots_dir=data_dir / "intent_graphs",
        audits_dir=data_dir / "audits",
        reports_dir=data_dir / "reports",
        traces_dir=data_dir / "traces",
        destination_aliases_path=data_dir / "destination_aliases.json",
        remediation_index_path=data_dir / "remediation_index.jsonl",
    )


def _env_flag(name: str, *, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, *, default: float) -> float:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


def _env_int(name: str, *, default: int) -> int:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def _env_csv(name: str, *, default: tuple[str, ...]) -> tuple[str, ...]:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    values = tuple(item.strip().lower() for item in raw_value.split(",") if item.strip())
    return values or default


def _env_csv_raw(name: str, *, default: tuple[str, ...]) -> tuple[str, ...]:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    values = tuple(item.strip() for item in raw_value.split(",") if item.strip())
    return values or default


def _env_json_dict(name: str) -> dict[str, str] | None:
    raw_value = os.environ.get(name)
    if raw_value is None or not raw_value.strip():
        return None
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    normalized: dict[str, str] = {}
    for key, item in value.items():
        key_text = str(key or "").strip()
        value_text = str(item or "").strip()
        if key_text and value_text:
            normalized[key_text] = value_text
    return normalized or None


def postgres_runtime_primary_url(settings: WorkspaceSettings) -> str:
    return settings.postgres_runtime_database_url or settings.database_url


def postgres_runtime_enabled(settings: WorkspaceSettings) -> bool:
    return bool(
        settings.enable_postgres_runtime
        or settings.postgres_runtime_database_url
        or settings.database_backend == "postgres"
    )


def postgres_runtime_url(settings: WorkspaceSettings) -> str:
    return postgres_runtime_primary_url(settings)
