from __future__ import annotations

import argparse
import csv
from datetime import datetime
from io import StringIO
import json
from pathlib import Path

from lsa.core.intent_graph import IntentGraph
from lsa.drift.comparator import DriftComparator
from lsa.drift.ebpf_observer import ObservationResult
from lsa.drift.models import ObservedEvent
from lsa.drift.signal_processor import load_events
from lsa.drift.trace_parser import load_trace_events
from lsa.remediation.llm_client import build_remediation_client
from lsa.services.audit_service import AuditService
from lsa.services.analytics_service import AnalyticsService, ControlPlaneAlertThresholds
from lsa.services.control_plane_alert_service import ControlPlaneAlertService
from lsa.services.control_plane_authorization_service import ControlPlaneAuthorizationService
from lsa.services.control_plane_backup_rehearsal_service import ControlPlaneBackupRehearsalService
from lsa.services.control_plane_backup_operations_service import ControlPlaneBackupOperationsService
from lsa.services.control_plane_backup_service import ControlPlaneBackupService
from lsa.services.control_plane_backup_validation_service import ControlPlaneBackupValidationService
from lsa.services.control_plane_canary_verifier_service import ControlPlaneCanaryVerifierService
from lsa.services.control_plane_cutover_promotion_service import ControlPlaneCutoverPromotionService
from lsa.services.control_plane_cutover_service import ControlPlaneCutoverService
from lsa.services.control_plane_cutover_readiness_service import ControlPlaneCutoverReadinessService
from lsa.services.control_plane_deployment_readiness_service import ControlPlaneDeploymentReadinessService
from lsa.services.control_plane_incident_narrative_service import ControlPlaneIncidentNarrativeService
from lsa.services.control_plane_live_workload_proof_validation_service import (
    ControlPlaneLiveWorkloadProofValidationService,
)
from lsa.services.control_plane_live_workload_target_validation_service import (
    ControlPlaneLiveWorkloadTargetValidationService,
)
from lsa.services.control_plane_maintenance_service import ControlPlaneMaintenanceService
from lsa.services.control_plane_operational_validation_service import ControlPlaneOperationalValidationService
from lsa.services.control_plane_operational_validation_evidence_service import ControlPlaneOperationalValidationEvidenceService
from lsa.services.control_plane_soak_validation_service import ControlPlaneSoakValidationService
from lsa.services.control_plane_soak_validation_evidence_service import ControlPlaneSoakValidationEvidenceService
from lsa.services.control_plane_observability_export_service import ControlPlaneObservabilityExportService
from lsa.services.control_plane_queue_validation_service import ControlPlaneQueueValidationService
from lsa.services.control_plane_runtime_rehearsal_service import ControlPlaneRuntimeRehearsalService
from lsa.services.control_plane_runtime_smoke_service import ControlPlaneRuntimeSmokeService
from lsa.services.control_plane_runtime_validation_service import ControlPlaneRuntimeValidationService
from lsa.services.control_plane_runtime_validation_review_service import (
    ControlPlaneRuntimeValidationReviewService,
)
from lsa.services.control_plane_trust_score_service import ControlPlaneTrustScoreService
from lsa.services.control_plane_workload_validation_service import ControlPlaneWorkloadValidationService
from lsa.services.control_plane_worker_recovery_validation_service import ControlPlaneWorkerRecoveryValidationService
from lsa.services.ingest_service import IngestService
from lsa.services.job_service import JobService
from lsa.services.live_workload_drift_proof_service import LiveWorkloadDriftProofService
from lsa.services.live_workload_proof_bundle_service import LiveWorkloadProofBundleService
from lsa.services.live_workload_target_profile_service import LiveWorkloadTargetProfileService
from lsa.services.metrics_service import ControlPlaneMetricsService
from lsa.services.privileged_api_audit_service import PrivilegedApiAuditService
from lsa.services.postgres_bootstrap_service import PostgresBootstrapService
from lsa.services.postgres_cutover_rehearsal_service import PostgresCutoverRehearsalService
from lsa.services.postgres_runtime_shadow_service import PostgresRuntimeShadowService
from lsa.services.postgres_target_service import PostgresTargetService
from lsa.services.remediation_index_service import RemediationIndexService
from lsa.services.runtime_validation_policy import RuntimeValidationPolicy, load_runtime_validation_policy_bundle
from lsa.services.trace_collection_service import TraceCollectionRequest, TraceCollectionService
from lsa.settings import resolve_workspace_settings
from lsa.storage.database import inspect_database_runtime_support
from lsa.storage.files import AuditRepository, JobRepository, SnapshotRepository, build_control_plane_runtime_bundle


settings = resolve_workspace_settings()
graph = IntentGraph()
runtime_bundle = build_control_plane_runtime_bundle(settings, graph=graph)
snapshot_repository = runtime_bundle.snapshot_repository
audit_repository = runtime_bundle.audit_repository
job_repository = runtime_bundle.job_repository
ingest_service = IngestService(graph=graph, snapshot_repository=snapshot_repository)
remediation_index_service = RemediationIndexService(
    settings.remediation_index_path,
    environment_name=settings.environment_name,
)
audit_service = AuditService(
    graph=graph,
    snapshot_repository=snapshot_repository,
    audit_repository=audit_repository,
    drift_comparator=DriftComparator(),
    remediation_client=build_remediation_client(settings),
    settings=settings,
    remediation_index_service=remediation_index_service,
)
trace_collection_service = TraceCollectionService(settings=settings)
analytics_service = AnalyticsService(
    job_repository=job_repository,
    default_environment_name=settings.environment_name,
    heartbeat_timeout_seconds=settings.worker_heartbeat_timeout_seconds,
    default_thresholds=ControlPlaneAlertThresholds(
        queue_warning_threshold=settings.analytics_queue_warning_threshold,
        queue_critical_threshold=settings.analytics_queue_critical_threshold,
        stale_worker_warning_threshold=settings.analytics_stale_worker_warning_threshold,
        stale_worker_critical_threshold=settings.analytics_stale_worker_critical_threshold,
        expired_lease_warning_threshold=settings.analytics_expired_lease_warning_threshold,
        expired_lease_critical_threshold=settings.analytics_expired_lease_critical_threshold,
        job_failure_rate_warning_threshold=settings.analytics_job_failure_rate_warning_threshold,
        job_failure_rate_critical_threshold=settings.analytics_job_failure_rate_critical_threshold,
        job_failure_rate_min_samples=settings.analytics_job_failure_rate_min_samples,
        oncall_conflict_warning_threshold=settings.analytics_oncall_conflict_warning_threshold,
        oncall_conflict_critical_threshold=settings.analytics_oncall_conflict_critical_threshold,
        oncall_pending_review_warning_threshold=settings.analytics_oncall_pending_review_warning_threshold,
        oncall_pending_review_critical_threshold=settings.analytics_oncall_pending_review_critical_threshold,
        oncall_pending_review_sla_hours=settings.analytics_oncall_pending_review_sla_hours,
        runtime_rehearsal_due_soon_age_hours=settings.analytics_runtime_rehearsal_due_soon_age_hours,
        runtime_rehearsal_warning_age_hours=settings.analytics_runtime_rehearsal_warning_age_hours,
        runtime_rehearsal_critical_age_hours=settings.analytics_runtime_rehearsal_critical_age_hours,
        live_workload_proof_due_soon_age_hours=settings.analytics_live_workload_proof_due_soon_age_hours,
        live_workload_proof_warning_age_hours=settings.analytics_live_workload_proof_warning_age_hours,
        live_workload_proof_critical_age_hours=settings.analytics_live_workload_proof_critical_age_hours,
        backup_rehearsal_due_soon_age_hours=settings.analytics_backup_rehearsal_due_soon_age_hours,
        backup_rehearsal_warning_age_hours=settings.analytics_backup_rehearsal_warning_age_hours,
        backup_rehearsal_critical_age_hours=settings.analytics_backup_rehearsal_critical_age_hours,
        backup_export_warning_age_hours=settings.analytics_backup_export_warning_age_hours,
        backup_export_critical_age_hours=settings.analytics_backup_export_critical_age_hours,
        observability_export_warning_age_hours=settings.analytics_observability_export_warning_age_hours,
        observability_export_critical_age_hours=settings.analytics_observability_export_critical_age_hours,
        privileged_api_audit_non_ok_warning_threshold=settings.analytics_privileged_api_audit_non_ok_warning_threshold,
        privileged_api_audit_non_ok_critical_threshold=settings.analytics_privileged_api_audit_non_ok_critical_threshold,
    ),
    runtime_validation_policy_path=str(settings.runtime_validation_policy_path),
    runtime_validation_reminder_interval_seconds=settings.control_plane_alert_reminder_interval_seconds,
    runtime_validation_escalation_interval_seconds=settings.control_plane_alert_escalation_interval_seconds,
    privileged_api_audit_service=PrivilegedApiAuditService(settings.privileged_api_audit_log_path),
)
authorization_service = ControlPlaneAuthorizationService(
    organization_name=settings.organization_name,
    environment_name=settings.environment_name,
    admin_roles=settings.authz_admin_roles,
    authz_enabled=settings.authz_enabled,
    allowed_organizations=settings.authz_allowed_organizations,
)
control_plane_alert_service = ControlPlaneAlertService(
    job_repository=job_repository,
    analytics_service=analytics_service,
    default_environment_name=settings.environment_name,
    window_days=settings.control_plane_alert_window_days,
    dedup_window_seconds=settings.control_plane_alert_dedup_window_seconds,
    reminder_interval_seconds=settings.control_plane_alert_reminder_interval_seconds,
    escalation_interval_seconds=settings.control_plane_alert_escalation_interval_seconds,
    policy_path=str(settings.oncall_policy_path),
    runtime_validation_policy_path=str(settings.runtime_validation_policy_path),
    required_approver_roles=settings.oncall_approval_required_roles,
    allow_self_approval=settings.oncall_allow_self_approval,
    sink_path=str(settings.control_plane_alert_sink_path),
    webhook_url=settings.control_plane_alert_webhook_url,
    escalation_webhook_url=settings.control_plane_alert_escalation_webhook_url,
    deployment_rejected_change_control_critical_age_hours=settings.analytics_deployment_rejected_change_control_critical_age_hours,
    authorization_service=authorization_service,
)
control_plane_backup_service = ControlPlaneBackupService(
    settings=settings,
    snapshot_repository=snapshot_repository,
    audit_repository=audit_repository,
    job_repository=job_repository,
)
job_service = JobService(
    job_repository=job_repository,
    audit_service=audit_service,
    trace_collection_service=trace_collection_service,
    worker_mode="standalone",
    heartbeat_timeout_seconds=settings.worker_heartbeat_timeout_seconds,
    worker_history_retention_days=settings.worker_history_retention_days,
    job_lease_history_retention_days=settings.job_lease_history_retention_days,
    history_prune_interval_seconds=settings.history_prune_interval_seconds,
    control_plane_alert_service=control_plane_alert_service,
    control_plane_alert_interval_seconds=settings.control_plane_alert_interval_seconds,
    control_plane_alerts_enabled=settings.control_plane_alerts_enabled,
    observability_export_interval_seconds=settings.observability_export_interval_seconds,
    live_workload_target_validation_interval_seconds=settings.live_workload_target_validation_interval_seconds,
    operational_validation_interval_seconds=settings.operational_validation_interval_seconds,
    deployment_readiness_required_for_job_submission=settings.job_submission_deployment_readiness_required,
    authorization_service=authorization_service,
)
control_plane_backup_operations_service = ControlPlaneBackupOperationsService(
    settings=settings,
    backup_service=control_plane_backup_service,
    job_repository=job_repository,
    job_service=job_service,
)
job_service.control_plane_backup_operations_service = control_plane_backup_operations_service
runtime_validation_review_service = ControlPlaneRuntimeValidationReviewService(
    settings=settings,
    job_service=job_service,
    job_repository=job_repository,
)
job_service.runtime_validation_review_service = runtime_validation_review_service
control_plane_alert_service.runtime_validation_review_service = runtime_validation_review_service
deployment_readiness_service = ControlPlaneDeploymentReadinessService(
    settings=settings,
    job_repository=job_repository,
    job_service=job_service,
)
analytics_service.deployment_readiness_service = deployment_readiness_service
job_service.deployment_readiness_service = deployment_readiness_service
control_plane_alert_service.deployment_readiness_service = deployment_readiness_service
metrics_service = ControlPlaneMetricsService(
    job_repository=job_repository,
    job_service=job_service,
    analytics_service=analytics_service,
    environment_name=settings.environment_name,
    worker_mode="standalone",
)
control_plane_observability_export_service = ControlPlaneObservabilityExportService(
    settings=settings,
    job_service=job_service,
    analytics_service=analytics_service,
    metrics_service=metrics_service,
    privileged_api_audit_service=PrivilegedApiAuditService(settings.privileged_api_audit_log_path),
)
job_service.control_plane_observability_export_service = control_plane_observability_export_service
control_plane_maintenance_service = ControlPlaneMaintenanceService(
    settings=settings,
    job_repository=job_repository,
    job_service=job_service,
    backup_service=control_plane_backup_service,
    worker_mode="standalone",
)
control_plane_cutover_service = ControlPlaneCutoverService(
    settings=settings,
    maintenance_service=control_plane_maintenance_service,
)
postgres_bootstrap_service = PostgresBootstrapService()
postgres_target_service = PostgresTargetService(bootstrap_service=postgres_bootstrap_service)
def _postgres_cutover_rehearsal_service() -> PostgresCutoverRehearsalService:
    return PostgresCutoverRehearsalService(
        job_service=job_service,
        bootstrap_service=postgres_bootstrap_service,
        target_service=postgres_target_service,
    )


def _control_plane_cutover_readiness_service() -> ControlPlaneCutoverReadinessService:
    return ControlPlaneCutoverReadinessService(
        settings=settings,
        job_repository=job_repository,
        bootstrap_service=postgres_bootstrap_service,
    )


def _control_plane_cutover_promotion_service() -> ControlPlaneCutoverPromotionService:
    return ControlPlaneCutoverPromotionService(
        settings=settings,
        job_service=job_service,
        readiness_service=_control_plane_cutover_readiness_service(),
    )


def _postgres_runtime_shadow_service() -> PostgresRuntimeShadowService:
    return PostgresRuntimeShadowService(
        settings=settings,
        source_job_repository=job_repository,
    )


def _control_plane_runtime_smoke_service() -> ControlPlaneRuntimeSmokeService:
    return ControlPlaneRuntimeSmokeService(
        settings=settings,
        snapshot_repository=snapshot_repository,
        audit_repository=audit_repository,
        job_repository=job_repository,
        job_service=job_service,
        now_factory=lambda: datetime.now().astimezone().isoformat(),
    )


def _control_plane_runtime_rehearsal_service() -> ControlPlaneRuntimeRehearsalService:
    return ControlPlaneRuntimeRehearsalService(
        settings=settings,
        job_repository=job_repository,
        job_service=job_service,
        runtime_smoke_service=_control_plane_runtime_smoke_service(),
        now_factory=lambda: datetime.now().astimezone().isoformat(),
    )


def _control_plane_backup_rehearsal_service() -> ControlPlaneBackupRehearsalService:
    return ControlPlaneBackupRehearsalService(
        settings=settings,
        backup_service=control_plane_backup_service,
        job_service=job_service,
        now_factory=lambda: datetime.now().astimezone().isoformat(),
    )


def _control_plane_runtime_validation_service() -> ControlPlaneRuntimeValidationService:
    runtime_policy_bundle = load_runtime_validation_policy_bundle(settings.runtime_validation_policy_path)
    runtime_policy = runtime_policy_bundle.resolve(
        environment_name=settings.environment_name,
        fallback=RuntimeValidationPolicy(
            due_soon_age_hours=settings.analytics_runtime_rehearsal_due_soon_age_hours,
            warning_age_hours=settings.analytics_runtime_rehearsal_warning_age_hours,
            critical_age_hours=settings.analytics_runtime_rehearsal_critical_age_hours,
            reminder_interval_seconds=settings.control_plane_alert_reminder_interval_seconds,
            escalation_interval_seconds=settings.control_plane_alert_escalation_interval_seconds,
        ),
    )
    return ControlPlaneRuntimeValidationService(
        job_repository=job_repository,
        environment_name=settings.environment_name,
        due_soon_age_hours=runtime_policy.due_soon_age_hours
        or settings.analytics_runtime_rehearsal_due_soon_age_hours,
        warning_age_hours=runtime_policy.warning_age_hours
        or settings.analytics_runtime_rehearsal_warning_age_hours,
        critical_age_hours=runtime_policy.critical_age_hours
        or settings.analytics_runtime_rehearsal_critical_age_hours,
        policy_source=runtime_policy_bundle.source_for(environment_name=settings.environment_name),
        reminder_interval_seconds=runtime_policy.reminder_interval_seconds,
        escalation_interval_seconds=runtime_policy.escalation_interval_seconds,
    )


def _control_plane_backup_validation_service() -> ControlPlaneBackupValidationService:
    return ControlPlaneBackupValidationService(
        job_repository=job_repository,
        environment_name=settings.environment_name,
        due_soon_age_hours=settings.analytics_backup_rehearsal_due_soon_age_hours,
        warning_age_hours=settings.analytics_backup_rehearsal_warning_age_hours,
        critical_age_hours=settings.analytics_backup_rehearsal_critical_age_hours,
    )


def _control_plane_live_workload_proof_validation_service() -> ControlPlaneLiveWorkloadProofValidationService:
    return ControlPlaneLiveWorkloadProofValidationService(
        job_repository=job_repository,
        environment_name=settings.environment_name,
        due_soon_age_hours=settings.analytics_live_workload_proof_due_soon_age_hours,
        warning_age_hours=settings.analytics_live_workload_proof_warning_age_hours,
        critical_age_hours=settings.analytics_live_workload_proof_critical_age_hours,
    )


def _control_plane_live_workload_target_validation_service() -> ControlPlaneLiveWorkloadTargetValidationService:
    return ControlPlaneLiveWorkloadTargetValidationService(
        settings=settings,
        job_repository=job_repository,
        job_service=job_service,
        live_workload_drift_proof_service=_live_workload_drift_proof_service(),
    )


def _live_workload_target_profile_service() -> LiveWorkloadTargetProfileService:
    return LiveWorkloadTargetProfileService(settings)


def _live_workload_proof_bundle_service() -> LiveWorkloadProofBundleService:
    return LiveWorkloadProofBundleService(
        settings=settings,
        job_repository=job_repository,
        job_service=job_service,
        target_validation_service=_control_plane_live_workload_target_validation_service(),
        proof_validation_service=_control_plane_live_workload_proof_validation_service(),
        operational_validation_evidence_service=_control_plane_operational_validation_evidence_service(),
        target_profile_service=_live_workload_target_profile_service(),
    )




def _control_plane_backup_operations_service() -> ControlPlaneBackupOperationsService:
    return control_plane_backup_operations_service


def _control_plane_observability_export_service() -> ControlPlaneObservabilityExportService:
    return control_plane_observability_export_service


def _control_plane_operational_validation_service() -> ControlPlaneOperationalValidationService:
    return ControlPlaneOperationalValidationService(
        settings=settings,
        job_service=job_service,
        runtime_rehearsal_service=_control_plane_runtime_rehearsal_service(),
        backup_rehearsal_service=_control_plane_backup_rehearsal_service(),
        backup_operations_service=_control_plane_backup_operations_service(),
        backup_validation_service=_control_plane_backup_validation_service(),
        live_workload_drift_proof_service=_live_workload_drift_proof_service(),
        live_workload_target_validation_service=_control_plane_live_workload_target_validation_service(),
        live_workload_proof_validation_service=_control_plane_live_workload_proof_validation_service(),
        observability_export_service=_control_plane_observability_export_service(),
        queue_validation_service=_control_plane_queue_validation_service(),
        workload_validation_service=_control_plane_workload_validation_service(),
        worker_recovery_validation_service=_control_plane_worker_recovery_validation_service(),
        deployment_readiness_service=_control_plane_deployment_readiness_service(),
        now_factory=lambda: datetime.now().astimezone().isoformat(),
    )


def _control_plane_operational_validation_evidence_service() -> ControlPlaneOperationalValidationEvidenceService:
    return ControlPlaneOperationalValidationEvidenceService(
        job_repository=job_repository,
        environment_name=settings.environment_name,
        warning_age_hours=settings.analytics_operational_validation_warning_age_hours,
        critical_age_hours=settings.analytics_operational_validation_critical_age_hours,
    )


def _control_plane_soak_validation_service() -> ControlPlaneSoakValidationService:
    return ControlPlaneSoakValidationService(
        settings=settings,
        job_service=job_service,
        operational_validation_service=_control_plane_operational_validation_service(),
        now_factory=lambda: datetime.now().astimezone().isoformat(),
    )


def _control_plane_soak_validation_evidence_service() -> ControlPlaneSoakValidationEvidenceService:
    return ControlPlaneSoakValidationEvidenceService(
        job_repository=job_repository,
        environment_name=settings.environment_name,
        warning_age_hours=settings.analytics_operational_validation_warning_age_hours,
        critical_age_hours=settings.analytics_operational_validation_critical_age_hours,
    )


def _control_plane_trust_score_service() -> ControlPlaneTrustScoreService:
    return ControlPlaneTrustScoreService(
        settings=settings,
        runtime_validation_service=_control_plane_runtime_validation_service(),
        live_workload_target_validation_service=_control_plane_live_workload_target_validation_service(),
        live_workload_proof_validation_service=_control_plane_live_workload_proof_validation_service(),
        operational_validation_evidence_service=_control_plane_operational_validation_evidence_service(),
        soak_validation_evidence_service=_control_plane_soak_validation_evidence_service(),
        backup_validation_service=_control_plane_backup_validation_service(),
        backup_operations_service=_control_plane_backup_operations_service(),
        observability_export_service=_control_plane_observability_export_service(),
        deployment_readiness_service=_control_plane_deployment_readiness_service(),
        runtime_validation_review_service=runtime_validation_review_service,
    )


def _control_plane_incident_narrative_service() -> ControlPlaneIncidentNarrativeService:
    return ControlPlaneIncidentNarrativeService(
        settings=settings,
        job_repository=job_repository,
        deployment_readiness_service=_control_plane_deployment_readiness_service(),
        trust_score_service=_control_plane_trust_score_service(),
    )


def _control_plane_canary_verifier_service() -> ControlPlaneCanaryVerifierService:
    return ControlPlaneCanaryVerifierService(
        settings=settings,
        job_service=job_service,
        live_workload_target_validation_service=_control_plane_live_workload_target_validation_service(),
        live_workload_drift_proof_service=_live_workload_drift_proof_service(),
        runtime_rehearsal_service=_control_plane_runtime_rehearsal_service(),
        deployment_readiness_service=_control_plane_deployment_readiness_service(),
        now_factory=lambda: datetime.now().astimezone().isoformat(),
    )


def _control_plane_queue_validation_service() -> ControlPlaneQueueValidationService:
    return ControlPlaneQueueValidationService(
        settings=settings,
        job_service=job_service,
        now_factory=lambda: datetime.now().astimezone().isoformat(),
    )


def _control_plane_workload_validation_service() -> ControlPlaneWorkloadValidationService:
    return ControlPlaneWorkloadValidationService(
        settings=settings,
        job_service=job_service,
        queue_validation_service=_control_plane_queue_validation_service(),
        now_factory=lambda: datetime.now().astimezone().isoformat(),
    )


def _control_plane_worker_recovery_validation_service() -> ControlPlaneWorkerRecoveryValidationService:
    return ControlPlaneWorkerRecoveryValidationService(
        settings=settings,
        job_service=job_service,
        now_factory=lambda: datetime.now().astimezone().isoformat(),
    )


def _live_workload_drift_proof_service() -> LiveWorkloadDriftProofService:
    return LiveWorkloadDriftProofService(
        settings=settings,
        ingest_service=ingest_service,
        audit_service=audit_service,
        job_service=job_service,
    )


job_service.live_workload_target_validation_service = _control_plane_live_workload_target_validation_service()


def _control_plane_deployment_readiness_service() -> ControlPlaneDeploymentReadinessService:
    return deployment_readiness_service


job_service.operational_validation_service = _control_plane_operational_validation_service()
job_service.operational_validation_evidence_service = _control_plane_operational_validation_evidence_service()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lsa", description="Living Systems Auditor CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="Build an intent graph snapshot from a codebase.")
    ingest.add_argument("repo_path")
    ingest.add_argument("--out", dest="output_path", required=False)
    ingest.add_argument("--no-persist", action="store_true")
    ingest.add_argument("--snapshot-id", required=False)

    audit = subparsers.add_parser("audit", help="Compare observed events against a saved snapshot.")
    audit.add_argument("snapshot_ref")
    audit.add_argument("events_path")
    audit.add_argument("--snapshot-id", action="store_true")
    audit.add_argument("--out-dir", default=None)
    audit.add_argument("--no-persist", action="store_true")
    audit.add_argument("--audit-id", required=False)

    audit_trace = subparsers.add_parser("audit-trace", help="Audit a raw trace file against a snapshot.")
    audit_trace.add_argument("snapshot_ref")
    audit_trace.add_argument("trace_path")
    audit_trace.add_argument("--snapshot-id", action="store_true")
    audit_trace.add_argument("--trace-format", default="auto")
    audit_trace.add_argument("--out-dir", default=None)
    audit_trace.add_argument("--no-persist", action="store_true")
    audit_trace.add_argument("--audit-id", required=False)

    collect_trace = subparsers.add_parser("collect-trace", help="Collect raw trace lines from an observer command.")
    collect_trace.add_argument("pid", type=int)
    collect_trace.add_argument("--program", default="ebpf/network_observer.bt")
    collect_trace.add_argument("--duration", type=float, default=None)
    collect_trace.add_argument("--max-events", type=int, default=None)
    collect_trace.add_argument("--out", required=False)
    collect_trace.add_argument("--symbol-map", required=False)

    collect_audit = subparsers.add_parser(
        "collect-audit",
        help="Collect a trace from a live PID and immediately audit it against a snapshot.",
    )
    collect_audit.add_argument("snapshot_ref")
    collect_audit.add_argument("pid", type=int)
    collect_audit.add_argument("--snapshot-id", action="store_true")
    collect_audit.add_argument("--program", default="ebpf/network_observer.bt")
    collect_audit.add_argument("--duration", type=float, default=None)
    collect_audit.add_argument("--max-events", type=int, default=None)
    collect_audit.add_argument("--trace-format", default="bpftrace")
    collect_audit.add_argument("--out", required=False)
    collect_audit.add_argument("--symbol-map", required=False)
    collect_audit.add_argument("--audit-id", required=False)
    collect_audit.add_argument("--no-persist", action="store_true")

    parse_trace = subparsers.add_parser("parse-trace", help="Convert a trace file into normalized JSON events.")
    parse_trace.add_argument("trace_path")
    parse_trace.add_argument("--trace-format", default="auto")
    parse_trace.add_argument("--out", required=False)

    worker = subparsers.add_parser("worker", help="Run a standalone queue worker for persisted audit jobs.")
    worker.add_argument("--poll-interval", type=float, default=0.1)
    worker.add_argument("--idle-timeout", type=float, default=None)
    worker.add_argument("--max-jobs", type=int, default=None)
    worker.add_argument("--once", action="store_true")

    subparsers.add_parser("list-snapshots", help="List persisted snapshot records.")
    subparsers.add_parser("list-audits", help="List persisted audit records.")
    list_remediation_reports = subparsers.add_parser("list-remediation-reports", help="List indexed remediation reports.")
    list_remediation_reports.add_argument("--limit", type=int, default=100)
    list_remediation_reports.add_argument("--function", default=None)
    list_remediation_reports.add_argument("--risk", default=None)
    list_remediation_reports.add_argument("--environment-name", default=None)
    subparsers.add_parser("list-jobs", help="List persisted job records.")
    subparsers.add_parser("list-workers", help="List persisted worker records.")
    worker_heartbeats = subparsers.add_parser("list-worker-heartbeats", help="List recorded heartbeats for a worker.")
    worker_heartbeats.add_argument("worker_id")
    worker_heartbeat_rollups = subparsers.add_parser(
        "list-worker-heartbeat-rollups",
        help="List daily heartbeat rollups for a worker.",
    )
    worker_heartbeat_rollups.add_argument("worker_id")
    job_lease_events = subparsers.add_parser("list-job-lease-events", help="List recorded lease events for a job.")
    job_lease_events.add_argument("job_id")
    job_lease_event_rollups = subparsers.add_parser(
        "list-job-lease-event-rollups",
        help="List daily lease-event rollups for a job.",
    )
    job_lease_event_rollups.add_argument("job_id")
    control_plane_analytics = subparsers.add_parser(
        "control-plane-analytics",
        help="Show operational trends for queue, workers, and lease activity.",
    )
    control_plane_analytics.add_argument("--days", type=int, default=30)
    control_plane_metrics = subparsers.add_parser(
        "control-plane-metrics",
        help="Render Prometheus-style control-plane metrics.",
    )
    control_plane_metrics.add_argument("--days", type=int, default=1)
    subparsers.add_parser(
        "control-plane-maintenance-mode",
        help="Show the current control-plane maintenance mode state.",
    )
    subparsers.add_parser(
        "control-plane-preflight",
        help="Show a guarded preflight report for control-plane maintenance work.",
    )
    control_plane_runtime_smoke = subparsers.add_parser(
        "run-control-plane-runtime-smoke",
        help="Exercise snapshot, audit, and job persistence against the live control-plane runtime backend.",
    )
    control_plane_runtime_smoke.add_argument("--by", required=True)
    control_plane_runtime_smoke.add_argument("--reason", default=None)
    control_plane_runtime_smoke.add_argument("--keep-artifacts", action="store_true")
    control_plane_runtime_rehearsal = subparsers.add_parser(
        "run-control-plane-runtime-rehearsal",
        help="Verify that the live control-plane runtime matches the expected backend and passes a smoke check.",
    )
    control_plane_runtime_rehearsal.add_argument("--by", required=True)
    control_plane_runtime_rehearsal.add_argument("--expected-backend", default="postgres")
    control_plane_runtime_rehearsal.add_argument("--reason", default=None)
    control_plane_runtime_rehearsal.add_argument("--keep-artifacts", action="store_true")
    control_plane_runtime_rehearsal.add_argument("--ignore-deployment-readiness", action="store_true")
    control_plane_backup_rehearsal = subparsers.add_parser(
        "run-control-plane-backup-rehearsal",
        help="Export, restore, and verify a control-plane backup in an isolated rehearsal workspace.",
    )
    control_plane_backup_rehearsal.add_argument("--by", required=True)
    control_plane_backup_rehearsal.add_argument("--reason", default=None)
    control_plane_backup_rehearsal.add_argument("--keep-artifacts", action="store_true")
    control_plane_operational_validation = subparsers.add_parser(
        "run-control-plane-operational-validation",
        help="Run runtime proof, backup proof, backup freshness, and readiness as one operational validation flow.",
    )
    control_plane_operational_validation.add_argument("--by", required=True)
    control_plane_operational_validation.add_argument("--expected-backend", default="postgres")
    control_plane_operational_validation.add_argument("--reason", default=None)
    control_plane_operational_validation.add_argument("--skip-backup-processing", action="store_true")
    control_plane_operational_validation.add_argument("--keep-artifacts", action="store_true")
    control_plane_operational_validation.add_argument("--skip-queue-validation", action="store_true")
    control_plane_operational_validation.add_argument("--skip-workload-validation", action="store_true")
    control_plane_operational_validation.add_argument("--skip-live-workload-drift-proof", action="store_true")
    control_plane_operational_validation.add_argument("--skip-worker-recovery-validation", action="store_true")
    control_plane_operational_validation.add_argument("--queue-success-jobs", type=int, default=2)
    control_plane_operational_validation.add_argument("--queue-failure-jobs", type=int, default=1)
    control_plane_operational_validation.add_argument("--queue-delay-seconds", type=float, default=0.0)
    control_plane_operational_validation.add_argument("--no-inline-queue-worker", action="store_true")
    control_plane_operational_validation.add_argument("--workload-rounds", type=int, default=3)
    control_plane_operational_validation.add_argument("--workload-maintenance-pause-jobs", type=int, default=3)
    control_plane_operational_validation.add_argument("--skip-maintenance-pause-injection", action="store_true")
    control_plane_soak_validation = subparsers.add_parser(
        "run-control-plane-soak-validation",
        help="Run repeated operational validation iterations and persist soak evidence.",
    )
    control_plane_soak_validation.add_argument("--by", required=True)
    control_plane_soak_validation.add_argument("--expected-backend", default="postgres")
    control_plane_soak_validation.add_argument("--reason", default=None)
    control_plane_soak_validation.add_argument("--target-profile", default=None)
    control_plane_soak_validation.add_argument("--iterations", type=int, default=3)
    control_plane_soak_validation.add_argument("--pause-seconds", type=float, default=2.0)
    control_plane_soak_validation.add_argument("--skip-backup-processing", action="store_true")
    control_plane_soak_validation.add_argument("--keep-artifacts", action="store_true")
    control_plane_soak_validation.add_argument("--skip-queue-validation", action="store_true")
    control_plane_soak_validation.add_argument("--skip-workload-validation", action="store_true")
    control_plane_soak_validation.add_argument("--skip-live-workload-drift-proof", action="store_true")
    control_plane_soak_validation.add_argument("--skip-worker-recovery-validation", action="store_true")
    control_plane_soak_validation.add_argument("--queue-success-jobs", type=int, default=2)
    control_plane_soak_validation.add_argument("--queue-failure-jobs", type=int, default=1)
    control_plane_soak_validation.add_argument("--queue-delay-seconds", type=float, default=0.0)
    control_plane_soak_validation.add_argument("--no-inline-queue-worker", action="store_true")
    control_plane_soak_validation.add_argument("--workload-rounds", type=int, default=3)
    control_plane_soak_validation.add_argument("--workload-maintenance-pause-jobs", type=int, default=3)
    control_plane_soak_validation.add_argument("--skip-maintenance-pause-injection", action="store_true")
    control_plane_queue_validation = subparsers.add_parser(
        "run-control-plane-queue-validation",
        help="Run a synthetic queue/worker drill using noop validation jobs.",
    )
    control_plane_queue_validation.add_argument("--by", required=True)
    control_plane_queue_validation.add_argument("--reason", default=None)
    control_plane_queue_validation.add_argument("--queue-success-jobs", type=int, default=2)
    control_plane_queue_validation.add_argument("--queue-failure-jobs", type=int, default=1)
    control_plane_queue_validation.add_argument("--queue-delay-seconds", type=float, default=0.0)
    control_plane_queue_validation.add_argument("--no-inline-queue-worker", action="store_true")
    live_workload_drift_proof = subparsers.add_parser(
        "run-live-workload-drift-proof",
        help="Run the sample workload live, emit collector-style traces, and prove drift detection end to end.",
    )
    live_workload_drift_proof.add_argument("--by", required=True)
    live_workload_drift_proof.add_argument("--reason", default=None)
    live_workload_drift_proof.add_argument("--no-persist", action="store_true")
    live_workload_drift_proof.add_argument("--snapshot-id", default=None)
    live_workload_drift_proof.add_argument("--audit-id", default=None)
    subparsers.add_parser(
        "control-plane-live-workload-target-validation",
        help="Probe the currently configured live workload proof targets and report whether they are reachable.",
    )
    run_live_workload_target_validation = subparsers.add_parser(
        "run-control-plane-live-workload-target-validation",
        help="Probe live workload proof targets, persist evidence, and report the result.",
    )
    run_live_workload_target_validation.add_argument("--by", required=True)
    run_live_workload_target_validation.add_argument("--reason", default=None)
    run_live_workload_target_validation.add_argument("--timeout-seconds", type=float, default=10.0)
    run_live_workload_target_profile_validation = subparsers.add_parser(
        "run-live-workload-target-profile-validation",
        help="Probe a named live workload target profile and persist the result.",
    )
    run_live_workload_target_profile_validation.add_argument("--profile", required=True)
    run_live_workload_target_profile_validation.add_argument("--by", required=True)
    run_live_workload_target_profile_validation.add_argument("--reason", default=None)
    run_live_workload_target_profile_validation.add_argument("--timeout-seconds", type=float, default=10.0)
    run_live_workload_target_profile_drift_proof = subparsers.add_parser(
        "run-live-workload-target-profile-drift-proof",
        help="Run live workload drift proof against a named target profile.",
    )
    run_live_workload_target_profile_drift_proof.add_argument("--profile", required=True)
    run_live_workload_target_profile_drift_proof.add_argument("--by", required=True)
    run_live_workload_target_profile_drift_proof.add_argument("--reason", default=None)
    run_live_workload_target_profile_drift_proof.add_argument("--no-persist", action="store_true")
    run_live_workload_target_profile_drift_proof.add_argument("--snapshot-id", default=None)
    run_live_workload_target_profile_drift_proof.add_argument("--audit-id", default=None)
    run_live_workload_target_profile_operational_validation = subparsers.add_parser(
        "run-live-workload-target-profile-operational-validation",
        help="Run one-shot operational validation against a named live workload target profile.",
    )
    run_live_workload_target_profile_operational_validation.add_argument("--profile", required=True)
    run_live_workload_target_profile_operational_validation.add_argument("--by", required=True)
    run_live_workload_target_profile_operational_validation.add_argument("--expected-backend", default="postgres")
    run_live_workload_target_profile_operational_validation.add_argument("--reason", default=None)
    run_live_workload_target_profile_operational_validation.add_argument("--skip-backup-processing", action="store_true")
    run_live_workload_target_profile_operational_validation.add_argument("--no-cleanup", action="store_true")
    run_live_workload_target_profile_operational_validation.add_argument("--skip-queue-validation", action="store_true")
    run_live_workload_target_profile_operational_validation.add_argument("--skip-workload-validation", action="store_true")
    run_live_workload_target_profile_operational_validation.add_argument("--skip-worker-recovery-validation", action="store_true")
    run_live_workload_target_profile_operational_validation.add_argument("--skip-live-workload-drift-proof", action="store_true")
    run_live_workload_target_profile_operational_validation.add_argument("--queue-success-jobs", type=int, default=2)
    run_live_workload_target_profile_operational_validation.add_argument("--queue-failure-jobs", type=int, default=1)
    run_live_workload_target_profile_operational_validation.add_argument("--queue-delay-seconds", type=float, default=0.0)
    run_live_workload_target_profile_operational_validation.add_argument("--no-inline-queue-worker", action="store_true")
    run_live_workload_target_profile_operational_validation.add_argument("--workload-rounds", type=int, default=3)
    run_live_workload_target_profile_canary_verify = subparsers.add_parser(
        "run-live-workload-target-profile-canary-verify",
        help="Run target validation, drift proof, and operational validation as one canary promotion verdict.",
    )
    run_live_workload_target_profile_canary_verify.add_argument("--profile", required=True)
    run_live_workload_target_profile_canary_verify.add_argument("--by", required=True)
    run_live_workload_target_profile_canary_verify.add_argument("--expected-backend", default="postgres")
    run_live_workload_target_profile_canary_verify.add_argument("--reason", default=None)
    run_live_workload_target_profile_canary_verify.add_argument("--skip-backup-processing", action="store_true")
    run_live_workload_target_profile_canary_verify.add_argument("--no-cleanup", action="store_true")
    run_live_workload_target_profile_canary_verify.add_argument("--skip-queue-validation", action="store_true")
    run_live_workload_target_profile_canary_verify.add_argument("--skip-workload-validation", action="store_true")
    run_live_workload_target_profile_canary_verify.add_argument("--skip-worker-recovery-validation", action="store_true")
    run_live_workload_target_profile_canary_verify.add_argument("--queue-success-jobs", type=int, default=2)
    run_live_workload_target_profile_canary_verify.add_argument("--queue-failure-jobs", type=int, default=1)
    run_live_workload_target_profile_canary_verify.add_argument("--queue-delay-seconds", type=float, default=0.0)
    run_live_workload_target_profile_canary_verify.add_argument("--no-inline-queue-worker", action="store_true")
    run_live_workload_target_profile_canary_verify.add_argument("--workload-rounds", type=int, default=3)
    run_live_workload_target_profile_canary_verify.add_argument("--workload-maintenance-pause-jobs", type=int, default=3)
    run_live_workload_target_profile_canary_verify.add_argument("--skip-maintenance-pause-injection", action="store_true")
    run_live_workload_target_profile_operational_validation.add_argument("--workload-maintenance-pause-jobs", type=int, default=3)
    run_live_workload_target_profile_operational_validation.add_argument("--skip-maintenance-pause-injection", action="store_true")
    subparsers.add_parser(
        "list-live-workload-target-profiles",
        help="List built-in and file-backed live workload target profiles.",
    )
    export_live_workload_proof_bundle = subparsers.add_parser(
        "export-live-workload-proof-bundle",
        help="Export a portable bundle with latest target validation, drift proof, and operational validation evidence.",
    )
    export_live_workload_proof_bundle.add_argument("--by", required=True)
    export_live_workload_proof_bundle.add_argument("--reason", default=None)
    subparsers.add_parser(
        "list-live-workload-proof-bundles",
        help="List exported live workload proof bundles.",
    )
    inspect_live_workload_proof_bundle = subparsers.add_parser(
        "inspect-live-workload-proof-bundle",
        help="Inspect an exported live workload proof bundle for metadata and integrity.",
    )
    inspect_live_workload_proof_bundle.add_argument("--path", required=True)
    prune_live_workload_proof_bundles = subparsers.add_parser(
        "prune-live-workload-proof-bundles",
        help="Prune exported live workload proof bundles older than the retention window.",
    )
    prune_live_workload_proof_bundles.add_argument("--by", required=True)
    prune_live_workload_proof_bundles.add_argument("--reason", default=None)
    prune_live_workload_proof_bundles.add_argument("--retention-days", type=int, default=None)
    delete_live_workload_proof_bundle = subparsers.add_parser(
        "delete-live-workload-proof-bundle",
        help="Delete a specific exported live workload proof bundle.",
    )
    delete_live_workload_proof_bundle.add_argument("--path", required=True)
    delete_live_workload_proof_bundle.add_argument("--by", required=True)
    delete_live_workload_proof_bundle.add_argument("--reason", default=None)
    subparsers.add_parser(
        "control-plane-runtime-validation",
        help="Show the latest runtime rehearsal evidence and whether it is missing, stale, failed, or healthy.",
    )
    subparsers.add_parser(
        "control-plane-backup-validation",
        help="Show the latest backup rehearsal evidence and whether it is missing, stale, failed, or healthy.",
    )
    subparsers.add_parser(
        "control-plane-live-workload-proof-validation",
        help="Show the latest live workload drift proof evidence and whether it is missing, stale, failed, or healthy.",
    )
    subparsers.add_parser(
        "control-plane-operational-validation-status",
        help="Show the latest operational validation evidence and whether it is fresh, stale, failed, or missing.",
    )
    subparsers.add_parser(
        "control-plane-soak-validation-status",
        help="Show the latest soak validation evidence and whether it is fresh, stale, failed, or missing.",
    )
    subparsers.add_parser(
        "control-plane-observability-export-validation",
        help="Show the latest observability export freshness state for the active environment.",
    )
    observability_export = subparsers.add_parser(
        "export-control-plane-observability",
        help="Export control-plane analytics, metrics, maintenance, alerts, and privileged audit summary as a JSON snapshot.",
    )
    observability_export.add_argument("--by", required=True)
    observability_export.add_argument("--reason", default=None)
    subparsers.add_parser(
        "list-control-plane-observability-exports",
        help="List exported control-plane observability snapshots.",
    )
    subparsers.add_parser(
        "control-plane-backup-export-validation",
        help="Show the latest backup export freshness state for the active environment.",
    )
    subparsers.add_parser(
        "list-control-plane-backups",
        help="List exported control-plane backup bundles.",
    )
    process_control_plane_backups = subparsers.add_parser(
        "process-control-plane-backups",
        help="Run scheduled backup export/prune processing immediately.",
    )
    process_control_plane_backups.add_argument("--by", required=True)
    process_control_plane_backups.add_argument("--reason", default=None)
    process_control_plane_backups.add_argument("--force", action="store_true")
    subparsers.add_parser(
        "control-plane-deployment-readiness",
        help="Show broader deployment readiness, including runtime-validation and change-control blockers.",
    )
    subparsers.add_parser(
        "control-plane-trust-score",
        help="Show current environment trust score derived from runtime, backup, proof, and readiness evidence.",
    )
    subparsers.add_parser(
        "control-plane-incident-narrative",
        help="Show a timeline-backed incident narrative summarizing current control-plane risk and actions.",
    )
    deployment_readiness_owner_team_queue = subparsers.add_parser(
        "control-plane-deployment-readiness-owner-team-queue",
        help="Summarize linked runtime-validation change-control debt by owner team.",
    )
    deployment_readiness_owner_team_queue.add_argument("--status", default=None)
    deployment_readiness_owner_team_queue.add_argument("--owner-team", default=None)
    deployment_readiness_owner_team_queue.add_argument("--assignment-state", default=None)
    list_runtime_validation_reviews = subparsers.add_parser(
        "list-control-plane-runtime-validation-reviews",
        help="List runtime-validation review requests derived from maintenance history.",
    )
    list_runtime_validation_reviews.add_argument("--status", default=None)
    list_runtime_validation_reviews.add_argument("--owner-team", default=None)
    list_runtime_validation_reviews.add_argument("--assignment-state", default=None)
    runtime_validation_review_queue = subparsers.add_parser(
        "control-plane-runtime-validation-review-queue",
        help="Summarize runtime-validation review backlog by owner team and assignment state.",
    )
    runtime_validation_review_queue.add_argument("--status", default=None)
    runtime_validation_review_queue.add_argument("--owner-team", default=None)
    runtime_validation_review_queue.add_argument("--assignment-state", default=None)
    export_runtime_validation_review_queue_csv = subparsers.add_parser(
        "export-control-plane-runtime-validation-review-queue-csv",
        help="Export the filtered runtime-validation review queue as CSV.",
    )
    export_runtime_validation_review_queue_csv.add_argument("--status", default=None)
    export_runtime_validation_review_queue_csv.add_argument("--owner-team", default=None)
    export_runtime_validation_review_queue_csv.add_argument("--assignment-state", default=None)
    export_deployment_readiness_owner_team_queue_csv = subparsers.add_parser(
        "export-control-plane-deployment-readiness-owner-team-queue-csv",
        help="Export the filtered deployment-readiness owner-team queue as CSV.",
    )
    export_deployment_readiness_owner_team_queue_csv.add_argument("--status", default=None)
    export_deployment_readiness_owner_team_queue_csv.add_argument("--owner-team", default=None)
    export_deployment_readiness_owner_team_queue_csv.add_argument("--assignment-state", default=None)
    list_runtime_validation_governance_requests = subparsers.add_parser(
        "list-control-plane-runtime-validation-governance-requests",
        help="List governance escalation requests derived from critical unassigned runtime-validation review debt.",
    )
    list_runtime_validation_governance_requests.add_argument("--status", default=None)
    list_runtime_validation_governance_requests.add_argument("--owner-team", default=None)
    list_runtime_validation_change_control_requests = subparsers.add_parser(
        "list-control-plane-runtime-validation-change-control-requests",
        help="List change-control requests derived from runtime-validation governance debt.",
    )
    list_runtime_validation_change_control_requests.add_argument("--status", default=None)
    list_runtime_validation_change_control_requests.add_argument("--owner-team", default=None)
    list_runtime_validation_change_control_requests.add_argument("--assignment-state", default=None)
    process_runtime_validation_reviews = subparsers.add_parser(
        "process-control-plane-runtime-validation-reviews",
        help="Open or auto-resolve runtime-validation review requests for the active environment.",
    )
    process_runtime_validation_reviews.add_argument("--by", default="system")
    process_runtime_validation_reviews.add_argument("--reason", default=None)
    process_runtime_validation_reviews.add_argument("--force", action="store_true")
    process_runtime_validation_governance = subparsers.add_parser(
        "process-control-plane-runtime-validation-governance-requests",
        help="Open or auto-resolve governance escalation requests for critical unassigned runtime-validation review debt.",
    )
    process_runtime_validation_governance.add_argument("--by", default="system")
    process_runtime_validation_governance.add_argument("--reason", default=None)
    process_runtime_validation_governance.add_argument("--force", action="store_true")
    process_runtime_validation_change_control = subparsers.add_parser(
        "process-control-plane-runtime-validation-change-control-requests",
        help="Open or auto-resolve change-control requests derived from runtime-validation governance debt.",
    )
    process_runtime_validation_change_control.add_argument("--by", default="system")
    process_runtime_validation_change_control.add_argument("--reason", default=None)
    process_runtime_validation_change_control.add_argument("--force", action="store_true")
    assign_runtime_validation_change_control = subparsers.add_parser(
        "assign-control-plane-runtime-validation-change-control-request",
        help="Assign a runtime-validation change-control request.",
    )
    assign_runtime_validation_change_control.add_argument("request_id")
    assign_runtime_validation_change_control.add_argument("--assigned-to", required=True)
    assign_runtime_validation_change_control.add_argument("--assigned-team", default=None)
    assign_runtime_validation_change_control.add_argument("--by", required=True)
    assign_runtime_validation_change_control.add_argument("--note", default=None)
    review_runtime_validation_change_control = subparsers.add_parser(
        "review-control-plane-runtime-validation-change-control-request",
        help="Approve or reject a runtime-validation change-control request.",
    )
    review_runtime_validation_change_control.add_argument("request_id")
    review_runtime_validation_change_control.add_argument("--decision", required=True)
    review_runtime_validation_change_control.add_argument("--by", required=True)
    review_runtime_validation_change_control.add_argument("--note", default=None)
    bulk_assign_runtime_validation_change_control = subparsers.add_parser(
        "bulk-assign-control-plane-runtime-validation-change-control-requests",
        help="Bulk assign filtered runtime-validation change-control requests.",
    )
    bulk_assign_runtime_validation_change_control.add_argument("--assigned-to", required=True)
    bulk_assign_runtime_validation_change_control.add_argument("--assigned-team", default=None)
    bulk_assign_runtime_validation_change_control.add_argument("--by", required=True)
    bulk_assign_runtime_validation_change_control.add_argument("--note", default=None)
    bulk_assign_runtime_validation_change_control.add_argument("--status", default=None)
    bulk_assign_runtime_validation_change_control.add_argument("--owner-team", default=None)
    bulk_assign_runtime_validation_change_control.add_argument("--assignment-state", default=None)
    bulk_review_runtime_validation_change_control = subparsers.add_parser(
        "bulk-review-control-plane-runtime-validation-change-control-requests",
        help="Bulk approve or reject filtered runtime-validation change-control requests.",
    )
    bulk_review_runtime_validation_change_control.add_argument("--decision", required=True)
    bulk_review_runtime_validation_change_control.add_argument("--by", required=True)
    bulk_review_runtime_validation_change_control.add_argument("--note", default=None)
    bulk_review_runtime_validation_change_control.add_argument("--status", default=None)
    bulk_review_runtime_validation_change_control.add_argument("--owner-team", default=None)
    bulk_review_runtime_validation_change_control.add_argument("--assignment-state", default=None)
    assign_runtime_validation_review = subparsers.add_parser(
        "assign-control-plane-runtime-validation-review",
        help="Assign an active runtime-validation review request to an owner.",
    )
    assign_runtime_validation_review.add_argument("review_id")
    assign_runtime_validation_review.add_argument("--assigned-to", required=True)
    assign_runtime_validation_review.add_argument("--assigned-team", default=None)
    assign_runtime_validation_review.add_argument("--by", required=True)
    assign_runtime_validation_review.add_argument("--note", default=None)
    bulk_assign_runtime_validation_reviews = subparsers.add_parser(
        "bulk-assign-control-plane-runtime-validation-reviews",
        help="Bulk assign filtered runtime-validation reviews.",
    )
    bulk_assign_runtime_validation_reviews.add_argument("--assigned-to", required=True)
    bulk_assign_runtime_validation_reviews.add_argument("--assigned-team", default=None)
    bulk_assign_runtime_validation_reviews.add_argument("--by", required=True)
    bulk_assign_runtime_validation_reviews.add_argument("--note", default=None)
    bulk_assign_runtime_validation_reviews.add_argument("--status", default=None)
    bulk_assign_runtime_validation_reviews.add_argument("--owner-team", default=None)
    bulk_assign_runtime_validation_reviews.add_argument("--assignment-state", default=None)
    resolve_runtime_validation_review = subparsers.add_parser(
        "resolve-control-plane-runtime-validation-review",
        help="Resolve an active runtime-validation review request.",
    )
    resolve_runtime_validation_review.add_argument("review_id")
    resolve_runtime_validation_review.add_argument("--by", required=True)
    resolve_runtime_validation_review.add_argument("--reason", default="manual_resolution")
    resolve_runtime_validation_review.add_argument("--note", default=None)
    bulk_resolve_runtime_validation_reviews = subparsers.add_parser(
        "bulk-resolve-control-plane-runtime-validation-reviews",
        help="Bulk resolve filtered runtime-validation reviews.",
    )
    bulk_resolve_runtime_validation_reviews.add_argument("--by", required=True)
    bulk_resolve_runtime_validation_reviews.add_argument("--reason", default="manual_resolution")
    bulk_resolve_runtime_validation_reviews.add_argument("--note", default=None)
    bulk_resolve_runtime_validation_reviews.add_argument("--status", default=None)
    bulk_resolve_runtime_validation_reviews.add_argument("--owner-team", default=None)
    bulk_resolve_runtime_validation_reviews.add_argument("--assignment-state", default=None)
    subparsers.add_parser(
        "control-plane-runtime-backend",
        help="Show runtime backend activation support for the current control-plane database.",
    )
    inspect_control_plane_runtime_backend = subparsers.add_parser(
        "inspect-control-plane-runtime-backend",
        help="Inspect runtime backend activation support for an arbitrary database URL.",
    )
    inspect_control_plane_runtime_backend.add_argument("--database-url", required=True)
    sync_postgres_runtime_shadow = subparsers.add_parser(
        "sync-postgres-runtime-shadow",
        help="Shadow-sync maintenance metadata and maintenance events into a Postgres runtime target.",
    )
    sync_postgres_runtime_shadow.add_argument("--target-database-url", required=True)
    sync_postgres_runtime_shadow.add_argument("--by", required=True)
    sync_postgres_runtime_shadow.add_argument("--reason", default=None)
    control_plane_cutover_preflight = subparsers.add_parser(
        "control-plane-cutover-preflight",
        help="Validate a target database URL and show the guarded cutover preflight.",
    )
    control_plane_cutover_preflight.add_argument("--target-database-url", required=True)
    inspect_postgres_bootstrap_package = subparsers.add_parser(
        "inspect-postgres-bootstrap-package",
        help="Inspect and verify a generated Postgres bootstrap package.",
    )
    inspect_postgres_bootstrap_package.add_argument("--package-dir", required=True)
    inspect_postgres_target = subparsers.add_parser(
        "inspect-postgres-target",
        help="Inspect a live Postgres target database against the shared control-plane schema contract.",
    )
    inspect_postgres_target.add_argument("--target-database-url", required=True)
    inspect_postgres_target.add_argument("--psql-executable", default="psql")
    plan_postgres_bootstrap_execution = subparsers.add_parser(
        "plan-postgres-bootstrap-execution",
        help="Build the execution plan for applying a Postgres bootstrap package.",
    )
    plan_postgres_bootstrap_execution.add_argument("--package-dir", required=True)
    plan_postgres_bootstrap_execution.add_argument("--target-database-url", required=True)
    plan_postgres_bootstrap_execution.add_argument("--artifact-target-root", default=None)
    plan_postgres_bootstrap_execution.add_argument("--psql-executable", default="psql")
    execute_postgres_bootstrap_package = subparsers.add_parser(
        "execute-postgres-bootstrap-package",
        help="Apply a Postgres bootstrap package or run it in dry-run mode.",
    )
    execute_postgres_bootstrap_package.add_argument("--package-dir", required=True)
    execute_postgres_bootstrap_package.add_argument("--target-database-url", required=True)
    execute_postgres_bootstrap_package.add_argument("--artifact-target-root", default=None)
    execute_postgres_bootstrap_package.add_argument("--psql-executable", default="psql")
    execute_postgres_bootstrap_package.add_argument("--dry-run", action="store_true")
    verify_postgres_bootstrap_package = subparsers.add_parser(
        "verify-postgres-bootstrap-package",
        help="Verify a Postgres bootstrap package against a live Postgres target database.",
    )
    verify_postgres_bootstrap_package.add_argument("--package-dir", required=True)
    verify_postgres_bootstrap_package.add_argument("--target-database-url", required=True)
    verify_postgres_bootstrap_package.add_argument("--psql-executable", default="psql")
    run_postgres_cutover_rehearsal = subparsers.add_parser(
        "run-postgres-cutover-rehearsal",
        help="Run an audited dry-run or apply-and-verify rehearsal for a Postgres cutover package.",
    )
    run_postgres_cutover_rehearsal.add_argument("--package-dir", required=True)
    run_postgres_cutover_rehearsal.add_argument("--target-database-url", required=True)
    run_postgres_cutover_rehearsal.add_argument("--by", required=True)
    run_postgres_cutover_rehearsal.add_argument("--reason", default=None)
    run_postgres_cutover_rehearsal.add_argument("--psql-executable", default="psql")
    run_postgres_cutover_rehearsal.add_argument("--artifact-target-root", default=None)
    run_postgres_cutover_rehearsal.add_argument("--apply-to-target", action="store_true")
    evaluate_control_plane_cutover_readiness = subparsers.add_parser(
        "evaluate-control-plane-cutover-readiness",
        help="Evaluate whether a cutover bundle and its rehearsals are ready for promotion.",
    )
    evaluate_control_plane_cutover_readiness.add_argument("--package-dir", required=True)
    evaluate_control_plane_cutover_readiness.add_argument("--target-database-url", required=True)
    evaluate_control_plane_cutover_readiness.add_argument("--rehearsal-max-age-hours", type=float, default=24.0)
    evaluate_control_plane_cutover_readiness.add_argument("--require-apply-rehearsal", action="store_true")
    evaluate_control_plane_cutover_readiness.add_argument("--skip-runtime-validation", action="store_true")
    evaluate_control_plane_cutover_readiness.add_argument("--skip-live-workload-target-validation", action="store_true")
    evaluate_control_plane_cutover_readiness.add_argument("--skip-live-workload-proof-validation", action="store_true")
    evaluate_control_plane_cutover_readiness.add_argument("--skip-backup-validation", action="store_true")
    decide_control_plane_cutover = subparsers.add_parser(
        "decide-control-plane-cutover",
        help="Record an audited approval, rejection, block, or override decision for a cutover package.",
    )
    decide_control_plane_cutover.add_argument("--package-dir", required=True)
    decide_control_plane_cutover.add_argument("--target-database-url", required=True)
    decide_control_plane_cutover.add_argument("--by", required=True)
    decide_control_plane_cutover.add_argument("--decision", choices=["approve", "reject"], default="approve")
    decide_control_plane_cutover.add_argument("--reason", default=None)
    decide_control_plane_cutover.add_argument("--note", default=None)
    decide_control_plane_cutover.add_argument("--rehearsal-max-age-hours", type=float, default=24.0)
    decide_control_plane_cutover.add_argument("--require-apply-rehearsal", action="store_true")
    decide_control_plane_cutover.add_argument("--skip-runtime-validation", action="store_true")
    decide_control_plane_cutover.add_argument("--skip-live-workload-target-validation", action="store_true")
    decide_control_plane_cutover.add_argument("--skip-live-workload-proof-validation", action="store_true")
    decide_control_plane_cutover.add_argument("--skip-backup-validation", action="store_true")
    decide_control_plane_cutover.add_argument("--allow-override", action="store_true")
    list_control_plane_maintenance_events = subparsers.add_parser(
        "list-control-plane-maintenance-events",
        help="List persisted control-plane maintenance events.",
    )
    list_control_plane_maintenance_events.add_argument("--limit", type=int, default=50)
    enable_control_plane_maintenance_mode = subparsers.add_parser(
        "enable-control-plane-maintenance-mode",
        help="Enable control-plane maintenance mode to pause worker job execution.",
    )
    enable_control_plane_maintenance_mode.add_argument("--by", required=True)
    enable_control_plane_maintenance_mode.add_argument("--reason", default=None)
    disable_control_plane_maintenance_mode = subparsers.add_parser(
        "disable-control-plane-maintenance-mode",
        help="Disable control-plane maintenance mode and resume normal API mutations and worker execution.",
    )
    disable_control_plane_maintenance_mode.add_argument("--by", required=True)
    disable_control_plane_maintenance_mode.add_argument("--reason", default=None)
    run_control_plane_maintenance_workflow = subparsers.add_parser(
        "run-control-plane-maintenance-workflow",
        help="Run the guarded control-plane maintenance workflow.",
    )
    run_control_plane_maintenance_workflow.add_argument("--out", required=True)
    run_control_plane_maintenance_workflow.add_argument("--by", required=True)
    run_control_plane_maintenance_workflow.add_argument("--reason", default=None)
    run_control_plane_maintenance_workflow.add_argument("--allow-running-jobs", action="store_true")
    run_control_plane_maintenance_workflow.add_argument("--keep-maintenance-enabled", action="store_true")
    prepare_control_plane_cutover_bundle = subparsers.add_parser(
        "prepare-control-plane-cutover-bundle",
        help="Run the maintenance workflow and write a cutover bundle for a target database.",
    )
    prepare_control_plane_cutover_bundle.add_argument("--out", required=True)
    prepare_control_plane_cutover_bundle.add_argument("--target-database-url", required=True)
    prepare_control_plane_cutover_bundle.add_argument("--by", required=True)
    prepare_control_plane_cutover_bundle.add_argument("--reason", default=None)
    prepare_control_plane_cutover_bundle.add_argument("--allow-running-jobs", action="store_true")
    prepare_control_plane_cutover_bundle.add_argument("--keep-maintenance-enabled", action="store_true")
    emit_control_plane_alerts = subparsers.add_parser(
        "emit-control-plane-alerts",
        help="Force emission of current control-plane alerts through configured targets.",
    )
    emit_control_plane_alerts.add_argument("--force", action="store_true")
    process_control_plane_alert_followups = subparsers.add_parser(
        "process-control-plane-alert-followups",
        help="Force reminder/escalation follow-up processing for active control-plane alerts.",
    )
    process_control_plane_alert_followups.add_argument("--force", action="store_true")
    list_control_plane_alerts = subparsers.add_parser(
        "list-control-plane-alerts",
        help="List persisted control-plane alert emissions.",
    )
    list_control_plane_alerts.add_argument("--limit", type=int, default=50)
    acknowledge_control_plane_alert = subparsers.add_parser(
        "acknowledge-control-plane-alert",
        help="Acknowledge a persisted control-plane alert.",
    )
    acknowledge_control_plane_alert.add_argument("alert_id")
    acknowledge_control_plane_alert.add_argument("--by", required=True)
    acknowledge_control_plane_alert.add_argument("--note", default=None)
    create_control_plane_alert_silence = subparsers.add_parser(
        "create-control-plane-alert-silence",
        help="Silence future control-plane alerts by alert key or finding code for a fixed duration.",
    )
    create_control_plane_alert_silence.add_argument("--by", required=True)
    create_control_plane_alert_silence.add_argument("--reason", required=True)
    create_control_plane_alert_silence.add_argument("--duration-minutes", type=int, required=True)
    create_control_plane_alert_silence.add_argument("--alert-key", default=None)
    create_control_plane_alert_silence.add_argument("--finding-code", default=None)
    list_control_plane_alert_silences = subparsers.add_parser(
        "list-control-plane-alert-silences",
        help="List control-plane alert silences.",
    )
    list_control_plane_alert_silences.add_argument("--active-only", action="store_true")
    cancel_control_plane_alert_silence = subparsers.add_parser(
        "cancel-control-plane-alert-silence",
        help="Cancel a control-plane alert silence.",
    )
    cancel_control_plane_alert_silence.add_argument("silence_id")
    cancel_control_plane_alert_silence.add_argument("--by", required=True)
    create_control_plane_oncall_schedule = subparsers.add_parser(
        "create-control-plane-oncall-schedule",
        help="Create a timezone-aware on-call route for control-plane alerts.",
    )
    create_control_plane_oncall_schedule.add_argument("--by", required=True)
    create_control_plane_oncall_schedule.add_argument("--environment", default=None)
    create_control_plane_oncall_schedule.add_argument("--creator-team", default=None)
    create_control_plane_oncall_schedule.add_argument("--creator-role", default=None)
    create_control_plane_oncall_schedule.add_argument("--change-reason", default=None)
    create_control_plane_oncall_schedule.add_argument("--approved-by", default=None)
    create_control_plane_oncall_schedule.add_argument("--approver-team", default=None)
    create_control_plane_oncall_schedule.add_argument("--approver-role", default=None)
    create_control_plane_oncall_schedule.add_argument("--approval-note", default=None)
    create_control_plane_oncall_schedule.add_argument("--team", required=True)
    create_control_plane_oncall_schedule.add_argument("--timezone", required=True)
    create_control_plane_oncall_schedule.add_argument("--weekdays", nargs="+", type=int, required=True)
    create_control_plane_oncall_schedule.add_argument("--start-time", required=True)
    create_control_plane_oncall_schedule.add_argument("--end-time", required=True)
    create_control_plane_oncall_schedule.add_argument("--priority", type=int, default=100)
    create_control_plane_oncall_schedule.add_argument("--rotation", default=None)
    create_control_plane_oncall_schedule.add_argument("--effective-start-date", default=None)
    create_control_plane_oncall_schedule.add_argument("--effective-end-date", default=None)
    create_control_plane_oncall_schedule.add_argument("--webhook-url", default=None)
    create_control_plane_oncall_schedule.add_argument("--escalation-webhook-url", default=None)
    submit_control_plane_oncall_change_request = subparsers.add_parser(
        "submit-control-plane-oncall-change-request",
        help="Submit a governed control-plane on-call change request.",
    )
    submit_control_plane_oncall_change_request.add_argument("--by", required=True)
    submit_control_plane_oncall_change_request.add_argument("--environment", default=None)
    submit_control_plane_oncall_change_request.add_argument("--creator-team", default=None)
    submit_control_plane_oncall_change_request.add_argument("--creator-role", default=None)
    submit_control_plane_oncall_change_request.add_argument("--change-reason", required=True)
    submit_control_plane_oncall_change_request.add_argument("--team", required=True)
    submit_control_plane_oncall_change_request.add_argument("--timezone", required=True)
    submit_control_plane_oncall_change_request.add_argument("--weekdays", nargs="+", type=int, required=True)
    submit_control_plane_oncall_change_request.add_argument("--start-time", required=True)
    submit_control_plane_oncall_change_request.add_argument("--end-time", required=True)
    submit_control_plane_oncall_change_request.add_argument("--priority", type=int, default=100)
    submit_control_plane_oncall_change_request.add_argument("--rotation", default=None)
    submit_control_plane_oncall_change_request.add_argument("--effective-start-date", default=None)
    submit_control_plane_oncall_change_request.add_argument("--effective-end-date", default=None)
    submit_control_plane_oncall_change_request.add_argument("--webhook-url", default=None)
    submit_control_plane_oncall_change_request.add_argument("--escalation-webhook-url", default=None)
    list_control_plane_oncall_change_requests = subparsers.add_parser(
        "list-control-plane-oncall-change-requests",
        help="List control-plane on-call change requests.",
    )
    list_control_plane_oncall_change_requests.add_argument("--status", default=None)
    review_control_plane_oncall_change_request = subparsers.add_parser(
        "review-control-plane-oncall-change-request",
        help="Approve or reject a pending control-plane on-call change request.",
    )
    review_control_plane_oncall_change_request.add_argument("request_id")
    review_control_plane_oncall_change_request.add_argument("--decision", required=True)
    review_control_plane_oncall_change_request.add_argument("--by", required=True)
    review_control_plane_oncall_change_request.add_argument("--reviewer-team", default=None)
    review_control_plane_oncall_change_request.add_argument("--reviewer-role", default=None)
    review_control_plane_oncall_change_request.add_argument("--note", default=None)
    assign_control_plane_oncall_change_request = subparsers.add_parser(
        "assign-control-plane-oncall-change-request",
        help="Assign a pending control-plane on-call change request to an owner.",
    )
    assign_control_plane_oncall_change_request.add_argument("request_id")
    assign_control_plane_oncall_change_request.add_argument("--assigned-to", required=True)
    assign_control_plane_oncall_change_request.add_argument("--assigned-team", default=None)
    assign_control_plane_oncall_change_request.add_argument("--by", required=True)
    assign_control_plane_oncall_change_request.add_argument("--note", default=None)
    list_control_plane_oncall_schedules = subparsers.add_parser(
        "list-control-plane-oncall-schedules",
        help="List control-plane on-call schedules.",
    )
    list_control_plane_oncall_schedules.add_argument("--active-only", action="store_true")
    resolve_control_plane_oncall_route = subparsers.add_parser(
        "resolve-control-plane-oncall-route",
        help="Preview the effective on-call route and ranked active candidates.",
    )
    resolve_control_plane_oncall_route.add_argument("--at", default=None)
    cancel_control_plane_oncall_schedule = subparsers.add_parser(
        "cancel-control-plane-oncall-schedule",
        help="Cancel a control-plane on-call schedule.",
    )
    cancel_control_plane_oncall_schedule.add_argument("schedule_id")
    cancel_control_plane_oncall_schedule.add_argument("--by", required=True)
    subparsers.add_parser(
        "control-plane-schema",
        help="Show the current control-plane schema version and applied migrations.",
    )
    subparsers.add_parser(
        "control-plane-schema-contract",
        help="Show the shared control-plane schema contract for runtime and cutover tooling.",
    )
    subparsers.add_parser(
        "migrate-control-plane-schema",
        help="Apply idempotent control-plane schema migrations and report the resulting version state.",
    )
    export_control_plane_backup = subparsers.add_parser(
        "export-control-plane-backup",
        help="Export the full control-plane state into a versioned JSON backup bundle.",
    )
    export_control_plane_backup.add_argument("--out", required=True)
    import_control_plane_backup = subparsers.add_parser(
        "import-control-plane-backup",
        help="Restore the full control-plane state from a versioned JSON backup bundle.",
    )
    import_control_plane_backup.add_argument("input_path")
    import_control_plane_backup.add_argument("--replace-existing", action="store_true")
    subparsers.add_parser("prune-history", help="Prune retained worker heartbeat and lease-event history.")

    return parser


def run_ingest(
    repo_path: str,
    output_path: str | None,
    *,
    persist: bool,
    snapshot_id: str | None,
) -> int:
    result = ingest_service.ingest(
        repo_path,
        persist=persist,
        output_path=output_path,
        snapshot_id=snapshot_id,
    )
    payload = {
        "node_count": result.snapshot.node_count,
        "edge_count": result.snapshot.edge_count,
    }
    if result.snapshot_path:
        payload["snapshot_path"] = result.snapshot_path
    if result.record:
        payload["snapshot_id"] = result.record.snapshot_id
        payload["created_at"] = result.record.created_at
    print(json.dumps(payload, indent=2))
    return 0


def run_audit(
    snapshot_ref: str,
    events_path: str,
    *,
    snapshot_is_id: bool,
    out_dir: str | None,
    persist: bool,
    audit_id: str | None,
) -> int:
    result = audit_service.audit(
        snapshot_id=snapshot_ref if snapshot_is_id else None,
        snapshot_path=None if snapshot_is_id else snapshot_ref,
        events=[ObservedEvent.from_dict(item.to_dict()) for item in load_events(events_path)],
        persist=persist,
        report_dir=out_dir,
        audit_id=audit_id,
    )
    payload = {
        "alert_count": len(result.alerts),
        "alerts": [alert.to_dict() for alert in result.alerts],
        "report_paths": result.report_paths,
        "snapshot_path": result.snapshot_path,
        "sessions": [session.to_dict() for session in result.sessions],
        "explanation": result.explanation.to_dict(),
    }
    if result.record:
        payload["audit_id"] = result.record.audit_id
    print(json.dumps(payload, indent=2))
    return 0


def run_audit_trace(
    snapshot_ref: str,
    trace_path: str,
    *,
    snapshot_is_id: bool,
    trace_format: str,
    out_dir: str | None,
    persist: bool,
    audit_id: str | None,
) -> int:
    result = audit_service.audit(
        snapshot_id=snapshot_ref if snapshot_is_id else None,
        snapshot_path=None if snapshot_is_id else snapshot_ref,
        events=load_trace_events(trace_path, trace_format=trace_format),
        persist=persist,
        report_dir=out_dir,
        audit_id=audit_id,
    )
    payload = {
        "alert_count": len(result.alerts),
        "alerts": [alert.to_dict() for alert in result.alerts],
        "report_paths": result.report_paths,
        "snapshot_path": result.snapshot_path,
        "sessions": [session.to_dict() for session in result.sessions],
        "explanation": result.explanation.to_dict(),
    }
    if result.record:
        payload["audit_id"] = result.record.audit_id
    print(json.dumps(payload, indent=2))
    return 0


def run_parse_trace(trace_path: str, trace_format: str, output_path: str | None) -> int:
    events = load_trace_events(trace_path, trace_format=trace_format)
    payload = [event.to_dict() for event in events]
    rendered = json.dumps(payload, indent=2)
    if output_path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0


def run_collect_trace(
    pid: int,
    program: str,
    *,
    output_path: str | None,
    duration: float | None,
    max_events: int | None,
    symbol_map_path: str | None = None,
) -> int:
    result = trace_collection_service.collect(
        _build_trace_collection_request(
            pid=pid,
            program=program,
            output_path=output_path,
            duration=duration,
            max_events=max_events,
            symbol_map_path=symbol_map_path,
        )
    )
    _print_observation_result(result)
    return 0


def run_collect_audit(
    snapshot_ref: str,
    pid: int,
    *,
    snapshot_is_id: bool,
    program: str,
    duration: float | None,
    max_events: int | None,
    trace_format: str,
    output_path: str | None,
    persist: bool,
    audit_id: str | None,
    symbol_map_path: str | None = None,
) -> int:
    observation = trace_collection_service.collect(
        _build_trace_collection_request(
            pid=pid,
            program=program,
            output_path=output_path,
            duration=duration,
            max_events=max_events,
            symbol_map_path=symbol_map_path,
        )
    )
    result = audit_service.audit(
        snapshot_id=snapshot_ref if snapshot_is_id else None,
        snapshot_path=None if snapshot_is_id else snapshot_ref,
        events=load_trace_events(observation.trace_path, trace_format=trace_format),
        persist=persist,
        audit_id=audit_id,
    )
    payload = {
        "trace_path": observation.trace_path,
        "trace_metadata_path": observation.metadata_path,
        "trace_symbol_map_path": observation.symbol_map_path,
        "trace_context_map_path": observation.context_map_path,
        "line_count": observation.line_count,
        "alert_count": len(result.alerts),
        "alerts": [alert.to_dict() for alert in result.alerts],
        "report_paths": result.report_paths,
        "sessions": [session.to_dict() for session in result.sessions],
        "explanation": result.explanation.to_dict(),
    }
    if result.record:
        payload["audit_id"] = result.record.audit_id
    print(json.dumps(payload, indent=2))
    return 0


def run_worker(
    *,
    poll_interval: float,
    idle_timeout: float | None,
    max_jobs: int | None,
    once: bool,
) -> int:
    job_service.poll_interval_seconds = poll_interval
    processed_jobs = job_service.run_foreground(
        max_jobs=1 if once else max_jobs,
        idle_timeout_seconds=idle_timeout,
    )
    payload = {
        "worker_mode": "standalone",
        "worker_id": job_service.worker_id(),
        "processed_jobs": processed_jobs,
        "active_workers": job_service.active_worker_count(),
        "queued_jobs": job_service.count_jobs_by_status("queued"),
        "running_jobs": job_service.count_jobs_by_status("running"),
        "completed_jobs": job_service.count_jobs_by_status("completed"),
        "failed_jobs": job_service.count_jobs_by_status("failed"),
    }
    print(json.dumps(payload, indent=2))
    return 0


def run_prune_history() -> int:
    payload = job_service.prune_history(force=True)
    print(json.dumps(payload, indent=2))
    return 0


def run_control_plane_schema() -> int:
    print(json.dumps(job_repository.schema_status(), indent=2))
    return 0


def run_control_plane_schema_contract() -> int:
    print(json.dumps(job_repository.schema_contract(), indent=2))
    return 0


def run_migrate_control_plane_schema() -> int:
    print(json.dumps(job_repository.migrate_schema(), indent=2))
    return 0


def run_export_control_plane_backup(*, output_path: str) -> int:
    summary = control_plane_backup_service.export_bundle(output_path)
    print(json.dumps(summary.to_dict(), indent=2))
    return 0


def run_import_control_plane_backup(*, input_path: str, replace_existing: bool) -> int:
    summary = control_plane_backup_service.import_bundle(input_path, replace_existing=replace_existing)
    print(json.dumps(summary.to_dict(), indent=2))
    return 0


def run_control_plane_analytics(*, days: int) -> int:
    payload = analytics_service.build_control_plane_analytics(days=days).to_dict()
    print(json.dumps(payload, indent=2))
    return 0


def run_control_plane_metrics(*, days: int) -> int:
    print(metrics_service.render_prometheus(days=days), end="")
    return 0


def run_control_plane_maintenance_mode() -> int:
    print(json.dumps(job_repository.maintenance_mode_status(), indent=2))
    return 0


def run_control_plane_preflight() -> int:
    print(json.dumps(control_plane_maintenance_service.build_preflight().to_dict(), indent=2))
    return 0


def run_control_plane_runtime_smoke(*, changed_by: str, reason: str | None, cleanup: bool) -> int:
    print(
        json.dumps(
            _control_plane_runtime_smoke_service().run(
                changed_by=changed_by,
                reason=reason,
                cleanup=cleanup,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_control_plane_runtime_rehearsal(
    *,
    changed_by: str,
    expected_backend: str,
    reason: str | None,
    cleanup: bool,
    ignore_deployment_readiness: bool,
) -> int:
    print(
        json.dumps(
            _control_plane_runtime_rehearsal_service().run(
                changed_by=changed_by,
                expected_backend=expected_backend,
                reason=reason,
                cleanup=cleanup,
                ignore_deployment_readiness=ignore_deployment_readiness,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_control_plane_backup_rehearsal(
    *,
    changed_by: str,
    reason: str | None,
    cleanup: bool,
) -> int:
    print(
        json.dumps(
            _control_plane_backup_rehearsal_service().run(
                changed_by=changed_by,
                reason=reason,
                cleanup=cleanup,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_control_plane_operational_validation(
    *,
    changed_by: str,
    expected_backend: str,
    reason: str | None,
    process_backups: bool,
    cleanup: bool,
    run_queue_validation: bool,
    run_workload_validation: bool,
    run_live_workload_drift_proof: bool,
    run_worker_recovery_validation: bool,
    queue_success_jobs: int,
    queue_failure_jobs: int,
    queue_delay_seconds: float,
    run_inline_queue_worker: bool,
    workload_rounds: int,
    workload_maintenance_pause_jobs: int,
    inject_maintenance_mode_pause: bool,
) -> int:
    print(
        json.dumps(
            _control_plane_operational_validation_service().run(
                changed_by=changed_by,
                expected_backend=expected_backend,
                reason=reason,
                process_backups=process_backups,
                cleanup=cleanup,
                run_queue_validation=run_queue_validation,
                run_workload_validation=run_workload_validation,
                run_live_workload_drift_proof=run_live_workload_drift_proof,
                run_worker_recovery_validation=run_worker_recovery_validation,
                queue_success_jobs=queue_success_jobs,
                queue_failure_jobs=queue_failure_jobs,
                queue_delay_seconds=queue_delay_seconds,
                run_inline_queue_worker=run_inline_queue_worker,
                workload_rounds=workload_rounds,
                workload_maintenance_pause_jobs=workload_maintenance_pause_jobs,
                inject_maintenance_mode_pause=inject_maintenance_mode_pause,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_control_plane_soak_validation(
    *,
    changed_by: str,
    expected_backend: str,
    reason: str | None,
    target_profile_name: str | None,
    iterations: int,
    pause_seconds: float,
    process_backups: bool,
    cleanup: bool,
    run_queue_validation: bool,
    run_workload_validation: bool,
    run_live_workload_drift_proof: bool,
    run_worker_recovery_validation: bool,
    queue_success_jobs: int,
    queue_failure_jobs: int,
    queue_delay_seconds: float,
    run_inline_queue_worker: bool,
    workload_rounds: int,
    workload_maintenance_pause_jobs: int,
    inject_maintenance_mode_pause: bool,
) -> int:
    print(
        json.dumps(
            _control_plane_soak_validation_service().run(
                changed_by=changed_by,
                expected_backend=expected_backend,
                reason=reason,
                target_profile_name=target_profile_name,
                iterations=iterations,
                pause_seconds=pause_seconds,
                process_backups=process_backups,
                cleanup=cleanup,
                run_queue_validation=run_queue_validation,
                run_workload_validation=run_workload_validation,
                run_live_workload_drift_proof=run_live_workload_drift_proof,
                run_worker_recovery_validation=run_worker_recovery_validation,
                queue_success_jobs=queue_success_jobs,
                queue_failure_jobs=queue_failure_jobs,
                queue_delay_seconds=queue_delay_seconds,
                run_inline_queue_worker=run_inline_queue_worker,
                workload_rounds=workload_rounds,
                workload_maintenance_pause_jobs=workload_maintenance_pause_jobs,
                inject_maintenance_mode_pause=inject_maintenance_mode_pause,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_control_plane_queue_validation(
    *,
    changed_by: str,
    reason: str | None,
    queue_success_jobs: int,
    queue_failure_jobs: int,
    queue_delay_seconds: float,
    run_inline_queue_worker: bool,
) -> int:
    print(
        json.dumps(
            _control_plane_queue_validation_service().run(
                changed_by=changed_by,
                reason=reason,
                success_jobs=queue_success_jobs,
                failure_jobs=queue_failure_jobs,
                delay_seconds=queue_delay_seconds,
                run_inline_worker=run_inline_queue_worker,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_live_workload_drift_proof(
    *,
    changed_by: str,
    reason: str | None,
    persist: bool,
    snapshot_id: str | None,
    audit_id: str | None,
) -> int:
    print(
        json.dumps(
            _live_workload_drift_proof_service().run(
                changed_by=changed_by,
                reason=reason,
                persist=persist,
                snapshot_id=snapshot_id,
                audit_id=audit_id,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_control_plane_runtime_validation() -> int:
    print(json.dumps(_control_plane_runtime_validation_service().build_summary().to_dict(), indent=2))
    return 0


def run_control_plane_live_workload_proof_validation() -> int:
    print(json.dumps(_control_plane_live_workload_proof_validation_service().build_summary().to_dict(), indent=2))
    return 0


def run_control_plane_live_workload_target_validation() -> int:
    print(json.dumps(_control_plane_live_workload_target_validation_service().build_summary().to_dict(), indent=2))
    return 0


def run_list_live_workload_target_profiles() -> int:
    print(
        json.dumps(
            [profile.to_dict() for profile in _live_workload_target_profile_service().list_profiles()],
            indent=2,
        )
    )
    return 0


def run_export_live_workload_proof_bundle(*, changed_by: str, reason: str | None) -> int:
    print(
        json.dumps(
            _live_workload_proof_bundle_service().export_bundle(
                changed_by=changed_by,
                reason=reason,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_list_live_workload_proof_bundles() -> int:
    print(
        json.dumps(
            [record.to_dict() for record in _live_workload_proof_bundle_service().list_bundles()],
            indent=2,
        )
    )
    return 0


def run_inspect_live_workload_proof_bundle(*, path: str) -> int:
    print(
        json.dumps(
            _live_workload_proof_bundle_service().inspect_bundle(path=path).to_dict(),
            indent=2,
        )
    )
    return 0


def run_prune_live_workload_proof_bundles(
    *,
    changed_by: str,
    reason: str | None,
    retention_days: int | None,
) -> int:
    print(
        json.dumps(
            _live_workload_proof_bundle_service().prune_bundles(
                changed_by=changed_by,
                reason=reason,
                retention_days=retention_days,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_delete_live_workload_proof_bundle(*, path: str, changed_by: str, reason: str | None) -> int:
    print(
        json.dumps(
            _live_workload_proof_bundle_service().delete_bundle(
                path=path,
                changed_by=changed_by,
                reason=reason,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_execute_control_plane_live_workload_target_validation(
    *,
    changed_by: str,
    reason: str | None,
    timeout_seconds: float,
) -> int:
    print(
        json.dumps(
            _control_plane_live_workload_target_validation_service().execute(
                changed_by=changed_by,
                reason=reason,
                timeout_seconds=timeout_seconds,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_execute_live_workload_target_profile_validation(
    *,
    profile: str,
    changed_by: str,
    reason: str | None,
    timeout_seconds: float,
) -> int:
    if _live_workload_target_profile_service().resolve(profile) is None:
        raise SystemExit(f"Live workload target profile not found: {profile}")
    print(
        json.dumps(
            _control_plane_live_workload_target_validation_service().execute(
                changed_by=changed_by,
                reason=reason,
                timeout_seconds=timeout_seconds,
                target_profile_name=profile,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_live_workload_target_profile_drift_proof(
    *,
    profile: str,
    changed_by: str,
    reason: str | None,
    persist: bool,
    snapshot_id: str | None,
    audit_id: str | None,
) -> int:
    if _live_workload_target_profile_service().resolve(profile) is None:
        raise SystemExit(f"Live workload target profile not found: {profile}")
    print(
        json.dumps(
            _live_workload_drift_proof_service().run(
                changed_by=changed_by,
                reason=reason,
                persist=persist,
                snapshot_id=snapshot_id,
                audit_id=audit_id,
                target_profile_name=profile,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_live_workload_target_profile_operational_validation(
    *,
    profile: str,
    changed_by: str,
    expected_backend: str,
    reason: str | None,
    process_backups: bool,
    cleanup: bool,
    run_queue_validation: bool,
    run_live_workload_drift_proof: bool,
    queue_success_jobs: int,
    queue_failure_jobs: int,
    queue_delay_seconds: float,
    run_inline_queue_worker: bool,
    run_workload_validation: bool,
    workload_rounds: int,
    workload_maintenance_pause_jobs: int,
    inject_maintenance_mode_pause: bool,
    run_worker_recovery_validation: bool,
) -> int:
    if _live_workload_target_profile_service().resolve(profile) is None:
        raise SystemExit(f"Live workload target profile not found: {profile}")
    print(
        json.dumps(
            _control_plane_operational_validation_service().run(
                changed_by=changed_by,
                expected_backend=expected_backend,
                reason=reason,
                process_backups=process_backups,
                cleanup=cleanup,
                run_queue_validation=run_queue_validation,
                run_live_workload_drift_proof=run_live_workload_drift_proof,
                queue_success_jobs=queue_success_jobs,
                queue_failure_jobs=queue_failure_jobs,
                queue_delay_seconds=queue_delay_seconds,
                run_inline_queue_worker=run_inline_queue_worker,
                run_workload_validation=run_workload_validation,
                workload_rounds=workload_rounds,
                workload_maintenance_pause_jobs=workload_maintenance_pause_jobs,
                inject_maintenance_mode_pause=inject_maintenance_mode_pause,
                run_worker_recovery_validation=run_worker_recovery_validation,
                target_profile_name=profile,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_live_workload_target_profile_canary_verify(
    *,
    profile: str,
    changed_by: str,
    expected_backend: str,
    reason: str | None,
    process_backups: bool,
    cleanup: bool,
    run_queue_validation: bool,
    run_workload_validation: bool,
    run_worker_recovery_validation: bool,
    queue_success_jobs: int,
    queue_failure_jobs: int,
    queue_delay_seconds: float,
    run_inline_queue_worker: bool,
    workload_rounds: int,
    workload_maintenance_pause_jobs: int,
    inject_maintenance_mode_pause: bool,
) -> int:
    if _live_workload_target_profile_service().resolve(profile) is None:
        raise SystemExit(f"Live workload target profile not found: {profile}")
    print(
        json.dumps(
            _control_plane_canary_verifier_service().run(
                changed_by=changed_by,
                target_profile_name=profile,
                expected_backend=expected_backend,
                reason=reason,
                process_backups=process_backups,
                cleanup=cleanup,
                run_queue_validation=run_queue_validation,
                run_workload_validation=run_workload_validation,
                run_worker_recovery_validation=run_worker_recovery_validation,
                queue_success_jobs=queue_success_jobs,
                queue_failure_jobs=queue_failure_jobs,
                queue_delay_seconds=queue_delay_seconds,
                run_inline_queue_worker=run_inline_queue_worker,
                workload_rounds=workload_rounds,
                workload_maintenance_pause_jobs=workload_maintenance_pause_jobs,
                inject_maintenance_mode_pause=inject_maintenance_mode_pause,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_control_plane_backup_validation() -> int:
    print(json.dumps(_control_plane_backup_validation_service().build_summary().to_dict(), indent=2))
    return 0


def run_control_plane_operational_validation_status() -> int:
    print(json.dumps(_control_plane_operational_validation_evidence_service().build_summary().to_dict(), indent=2))
    return 0


def run_control_plane_soak_validation_status() -> int:
    print(json.dumps(_control_plane_soak_validation_evidence_service().build_summary().to_dict(), indent=2))
    return 0


def run_control_plane_observability_export_validation() -> int:
    print(json.dumps(_control_plane_observability_export_service().latest_export_validation().to_dict(), indent=2))
    return 0


def run_control_plane_trust_score() -> int:
    print(json.dumps(_control_plane_trust_score_service().build_summary().to_dict(), indent=2))
    return 0


def run_control_plane_incident_narrative() -> int:
    print(json.dumps(_control_plane_incident_narrative_service().build_summary().to_dict(), indent=2))
    return 0


def run_control_plane_observability_export(*, changed_by: str, reason: str | None) -> int:
    print(
        json.dumps(
            control_plane_observability_export_service.export_snapshot(
                changed_by=changed_by,
                reason=reason,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_list_control_plane_observability_exports() -> int:
    print(
        json.dumps(
            [record.to_dict() for record in _control_plane_observability_export_service().list_exports()],
            indent=2,
        )
    )
    return 0


def run_control_plane_backup_export_validation() -> int:
    print(json.dumps(_control_plane_backup_operations_service().latest_backup_export_validation().to_dict(), indent=2))
    return 0


def run_list_control_plane_backups() -> int:
    print(
        json.dumps(
            [record.to_dict() for record in _control_plane_backup_operations_service().list_backup_bundles()],
            indent=2,
        )
    )
    return 0


def run_process_control_plane_backups(
    *,
    changed_by: str,
    reason: str | None,
    force: bool,
) -> int:
    print(
        json.dumps(
            _control_plane_backup_operations_service().process_scheduled_backups(
                changed_by=changed_by,
                reason=reason,
                force=force,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_control_plane_deployment_readiness() -> int:
    print(json.dumps(_control_plane_deployment_readiness_service().evaluate().to_dict(), indent=2))
    return 0


def _render_runtime_validation_review_queue_csv(
    *,
    status: str | None,
    owner_team: str | None,
    assignment_state: str | None,
) -> str:
    summary = job_service.runtime_validation_review_queue_summary(
        status=status,
        owner_team=owner_team,
        assignment_state=assignment_state,
    )
    if summary is None:
        raise RuntimeError("Runtime-validation review service is not configured.")
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "review_id",
            "environment_name",
            "status",
            "owner_team",
            "assigned_to",
            "assigned_to_team",
            "opened_at",
            "opened_by",
            "due_in_hours",
            "next_due_at",
            "policy_source",
            "summary",
        ]
    )
    for review in summary.reviews:
        writer.writerow(
            [
                review.review_id,
                review.environment_name,
                review.status,
                review.owner_team or "",
                review.assigned_to or "",
                review.assigned_to_team or "",
                review.opened_at,
                review.opened_by,
                "" if review.due_in_hours is None else review.due_in_hours,
                review.next_due_at or "",
                review.policy_source,
                review.summary,
            ]
        )
    return output.getvalue()


def run_list_control_plane_runtime_validation_reviews(
    *,
    status: str | None,
    owner_team: str | None,
    assignment_state: str | None,
) -> int:
    print(
        json.dumps(
            [
                record.to_dict()
                for record in job_service.list_runtime_validation_reviews(
                    status=status,
                    owner_team=owner_team,
                    assignment_state=assignment_state,
                )
            ],
            indent=2,
        )
    )
    return 0


def run_control_plane_runtime_validation_review_queue(
    *,
    status: str | None,
    owner_team: str | None,
    assignment_state: str | None,
) -> int:
    summary = job_service.runtime_validation_review_queue_summary(
        status=status,
        owner_team=owner_team,
        assignment_state=assignment_state,
    )
    if summary is None:
        raise RuntimeError("Runtime-validation review service is not configured.")
    print(json.dumps(summary.to_dict(), indent=2))
    return 0


def run_export_control_plane_runtime_validation_review_queue_csv(
    *,
    status: str | None,
    owner_team: str | None,
    assignment_state: str | None,
) -> int:
    print(
        _render_runtime_validation_review_queue_csv(
            status=status,
            owner_team=owner_team,
            assignment_state=assignment_state,
        ),
        end="",
    )
    return 0


def run_list_control_plane_runtime_validation_governance_requests(
    *,
    status: str | None,
    owner_team: str | None,
) -> int:
    print(
        json.dumps(
            [
                record.to_dict()
                for record in job_service.list_runtime_validation_governance_requests(
                    status=status,
                    owner_team=owner_team,
                )
            ],
            indent=2,
        )
    )
    return 0


def run_list_control_plane_runtime_validation_change_control_requests(
    *,
    status: str | None,
    owner_team: str | None,
    assignment_state: str | None = None,
) -> int:
    print(
        json.dumps(
            [
                record.to_dict()
                for record in job_service.list_runtime_validation_change_control_requests(
                    status=status,
                    owner_team=owner_team,
                    assignment_state=assignment_state,
                )
            ],
            indent=2,
        )
    )
    return 0


def run_control_plane_deployment_readiness_owner_team_queue(
    *,
    status: str | None,
    owner_team: str | None,
    assignment_state: str | None,
) -> int:
    summary = job_service.runtime_validation_change_control_queue_summary(
        status=status,
        owner_team=owner_team,
        assignment_state=assignment_state,
    )
    if summary is None:
        raise RuntimeError("Runtime-validation review service is not configured.")
    print(json.dumps(summary.to_dict(), indent=2))
    return 0


def run_export_control_plane_deployment_readiness_owner_team_queue_csv(
    *,
    status: str | None,
    owner_team: str | None,
    assignment_state: str | None,
) -> int:
    summary = job_service.runtime_validation_change_control_queue_summary(
        status=status,
        owner_team=owner_team,
        assignment_state=assignment_state,
    )
    if summary is None:
        raise RuntimeError("Runtime-validation review service is not configured.")
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "request_id",
            "environment_name",
            "status",
            "owner_team",
            "assigned_to",
            "assigned_to_team",
            "opened_at",
            "opened_by",
            "governance_request_id",
            "review_id",
            "policy_source",
            "summary",
        ]
    )
    for request in summary.requests:
        writer.writerow(
            [
                request.request_id,
                request.environment_name,
                request.status,
                request.owner_team or "",
                request.assigned_to or "",
                request.assigned_to_team or "",
                request.opened_at,
                request.opened_by,
                request.governance_request_id,
                request.review_id,
                request.policy_source,
                request.summary,
            ]
        )
    print(output.getvalue(), end="")
    return 0


def run_process_control_plane_runtime_validation_reviews(
    *,
    changed_by: str,
    reason: str | None,
    force: bool,
) -> int:
    records = job_service.process_runtime_validation_reviews(
        changed_by=changed_by,
        reason=reason,
        force=force,
    )
    print(json.dumps([record.to_dict() for record in records], indent=2))
    return 0


def run_process_control_plane_runtime_validation_governance_requests(
    *,
    changed_by: str,
    reason: str | None,
    force: bool,
) -> int:
    records = job_service.process_runtime_validation_governance(
        changed_by=changed_by,
        reason=reason,
        force=force,
    )
    print(json.dumps([record.to_dict() for record in records], indent=2))
    return 0


def run_process_control_plane_runtime_validation_change_control_requests(
    *,
    changed_by: str,
    reason: str | None,
    force: bool,
) -> int:
    records = job_service.process_runtime_validation_change_control(
        changed_by=changed_by,
        reason=reason,
        force=force,
    )
    print(json.dumps([record.to_dict() for record in records], indent=2))
    return 0


def run_assign_control_plane_runtime_validation_change_control_request(
    *,
    request_id: str,
    assigned_to: str,
    assigned_to_team: str | None,
    assigned_by: str,
    assignment_note: str | None,
) -> int:
    print(
        json.dumps(
            job_service.assign_runtime_validation_change_control_request(
                request_id=request_id,
                assigned_to=assigned_to,
                assigned_to_team=assigned_to_team,
                assigned_by=assigned_by,
                assignment_note=assignment_note,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_bulk_assign_control_plane_runtime_validation_change_control_requests(
    *,
    assigned_to: str,
    assigned_to_team: str | None,
    assigned_by: str,
    assignment_note: str | None,
    status: str | None,
    owner_team: str | None,
    assignment_state: str | None,
) -> int:
    print(
        json.dumps(
            job_service.bulk_assign_runtime_validation_change_control_requests(
                assigned_to=assigned_to,
                assigned_to_team=assigned_to_team,
                assigned_by=assigned_by,
                assignment_note=assignment_note,
                status=status,
                owner_team=owner_team,
                assignment_state=assignment_state,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_review_control_plane_runtime_validation_change_control_request(
    *,
    request_id: str,
    decision: str,
    decided_by: str,
    decision_note: str | None,
) -> int:
    print(
        json.dumps(
            job_service.decide_runtime_validation_change_control_request(
                request_id=request_id,
                decision=decision,
                decided_by=decided_by,
                decision_note=decision_note,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_bulk_review_control_plane_runtime_validation_change_control_requests(
    *,
    decision: str,
    decided_by: str,
    decision_note: str | None,
    status: str | None,
    owner_team: str | None,
    assignment_state: str | None,
) -> int:
    print(
        json.dumps(
            job_service.bulk_decide_runtime_validation_change_control_requests(
                decision=decision,
                decided_by=decided_by,
                decision_note=decision_note,
                status=status,
                owner_team=owner_team,
                assignment_state=assignment_state,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_assign_control_plane_runtime_validation_review(
    *,
    review_id: str,
    assigned_to: str,
    assigned_to_team: str | None,
    assigned_by: str,
    assignment_note: str | None,
) -> int:
    record = job_service.assign_runtime_validation_review(
        review_id=review_id,
        assigned_to=assigned_to,
        assigned_to_team=assigned_to_team,
        assigned_by=assigned_by,
        assignment_note=assignment_note,
    )
    print(json.dumps(record.to_dict(), indent=2))
    return 0


def run_bulk_assign_control_plane_runtime_validation_reviews(
    *,
    assigned_to: str,
    assigned_to_team: str | None,
    assigned_by: str,
    assignment_note: str | None,
    status: str | None,
    owner_team: str | None,
    assignment_state: str | None,
) -> int:
    result = job_service.bulk_assign_runtime_validation_reviews(
        assigned_to=assigned_to,
        assigned_to_team=assigned_to_team,
        assigned_by=assigned_by,
        assignment_note=assignment_note,
        status=status,
        owner_team=owner_team,
        assignment_state=assignment_state,
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0


def run_resolve_control_plane_runtime_validation_review(
    *,
    review_id: str,
    resolved_by: str,
    resolution_reason: str,
    resolution_note: str | None,
) -> int:
    record = job_service.resolve_runtime_validation_review(
        review_id=review_id,
        resolved_by=resolved_by,
        resolution_note=resolution_note,
        resolution_reason=resolution_reason,
    )
    print(json.dumps(record.to_dict(), indent=2))
    return 0


def run_bulk_resolve_control_plane_runtime_validation_reviews(
    *,
    resolved_by: str,
    resolution_reason: str,
    resolution_note: str | None,
    status: str | None,
    owner_team: str | None,
    assignment_state: str | None,
) -> int:
    result = job_service.bulk_resolve_runtime_validation_reviews(
        resolved_by=resolved_by,
        resolution_reason=resolution_reason,
        resolution_note=resolution_note,
        status=status,
        owner_team=owner_team,
        assignment_state=assignment_state,
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0


def run_control_plane_runtime_backend() -> int:
    print(json.dumps(job_repository.database_status(), indent=2))
    return 0


def run_inspect_control_plane_runtime_backend(*, database_url: str) -> int:
    print(
        json.dumps(
            inspect_database_runtime_support(
                root_dir=settings.root_dir,
                default_path=settings.database_path,
                raw_url=database_url,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_sync_postgres_runtime_shadow(
    *,
    target_database_url: str,
    changed_by: str,
    reason: str | None,
) -> int:
    print(
        json.dumps(
            _postgres_runtime_shadow_service().sync_control_plane_slice(
                target_database_url=target_database_url,
                changed_by=changed_by,
                reason=reason,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_control_plane_cutover_preflight(*, target_database_url: str) -> int:
    print(
        json.dumps(
            control_plane_cutover_service.build_preflight(target_database_url=target_database_url).to_dict(),
            indent=2,
        )
    )
    return 0


def run_inspect_postgres_bootstrap_package(*, package_dir: str) -> int:
    print(json.dumps(postgres_bootstrap_service.inspect_package(package_dir=package_dir).to_dict(), indent=2))
    return 0


def run_inspect_postgres_target(*, target_database_url: str, psql_executable: str) -> int:
    print(
        json.dumps(
            postgres_target_service.inspect_target(
                target_database_url=target_database_url,
                psql_executable=psql_executable,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_plan_postgres_bootstrap_execution(
    *,
    package_dir: str,
    target_database_url: str,
    artifact_target_root: str | None,
    psql_executable: str,
) -> int:
    print(
        json.dumps(
            postgres_bootstrap_service.build_execution_plan(
                package_dir=package_dir,
                target_database_url=target_database_url,
                artifact_target_root=artifact_target_root,
                psql_executable=psql_executable,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_execute_postgres_bootstrap_package(
    *,
    package_dir: str,
    target_database_url: str,
    artifact_target_root: str | None,
    psql_executable: str,
    dry_run: bool,
) -> int:
    print(
        json.dumps(
            postgres_bootstrap_service.execute_package(
                package_dir=package_dir,
                target_database_url=target_database_url,
                artifact_target_root=artifact_target_root,
                psql_executable=psql_executable,
                dry_run=dry_run,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_verify_postgres_bootstrap_package(
    *,
    package_dir: str,
    target_database_url: str,
    psql_executable: str,
) -> int:
    print(
        json.dumps(
            postgres_target_service.verify_bootstrap_package_against_target(
                package_dir=package_dir,
                target_database_url=target_database_url,
                psql_executable=psql_executable,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_postgres_cutover_rehearsal(
    *,
    package_dir: str,
    target_database_url: str,
    changed_by: str,
    reason: str | None,
    psql_executable: str,
    artifact_target_root: str | None,
    apply_to_target: bool,
) -> int:
    print(
        json.dumps(
            _postgres_cutover_rehearsal_service().execute_rehearsal(
                package_dir=package_dir,
                target_database_url=target_database_url,
                changed_by=changed_by,
                reason=reason,
                psql_executable=psql_executable,
                artifact_target_root=artifact_target_root,
                apply_to_target=apply_to_target,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_evaluate_control_plane_cutover_readiness(
    *,
    package_dir: str,
    target_database_url: str,
    rehearsal_max_age_hours: float,
    require_apply_rehearsal: bool,
    require_runtime_validation: bool | None = None,
    require_live_workload_target_validation: bool | None = None,
    require_live_workload_proof_validation: bool | None = None,
    require_backup_validation: bool | None = None,
) -> int:
    print(
        json.dumps(
            _control_plane_cutover_readiness_service().evaluate(
                package_dir=package_dir,
                target_database_url=target_database_url,
                rehearsal_max_age_hours=rehearsal_max_age_hours,
                require_apply_rehearsal=require_apply_rehearsal,
                require_runtime_validation=require_runtime_validation,
                require_live_workload_target_validation=require_live_workload_target_validation,
                require_live_workload_proof_validation=require_live_workload_proof_validation,
                require_backup_validation=require_backup_validation,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_decide_control_plane_cutover(
    *,
    package_dir: str,
    target_database_url: str,
    changed_by: str,
    requested_decision: str,
    reason: str | None,
    decision_note: str | None,
    rehearsal_max_age_hours: float,
    require_apply_rehearsal: bool,
    require_runtime_validation: bool | None = None,
    require_live_workload_target_validation: bool | None = None,
    require_live_workload_proof_validation: bool | None = None,
    require_backup_validation: bool | None = None,
    allow_override: bool,
) -> int:
    print(
        json.dumps(
            _control_plane_cutover_promotion_service().decide(
                package_dir=package_dir,
                target_database_url=target_database_url,
                changed_by=changed_by,
                requested_decision=requested_decision,
                reason=reason,
                decision_note=decision_note,
                rehearsal_max_age_hours=rehearsal_max_age_hours,
                require_apply_rehearsal=require_apply_rehearsal,
                require_runtime_validation=require_runtime_validation,
                require_live_workload_target_validation=require_live_workload_target_validation,
                require_live_workload_proof_validation=require_live_workload_proof_validation,
                require_backup_validation=require_backup_validation,
                allow_override=allow_override,
            ).to_dict(),
            indent=2,
        )
    )
    return 0


def run_list_control_plane_maintenance_events(*, limit: int) -> int:
    print(json.dumps([record.to_dict() for record in job_service.list_control_plane_maintenance_events(limit=limit)], indent=2))
    return 0


def run_enable_control_plane_maintenance_mode(*, changed_by: str, reason: str | None) -> int:
    print(json.dumps(job_service.enable_maintenance_mode(changed_by=changed_by, reason=reason), indent=2))
    return 0


def run_disable_control_plane_maintenance_mode(*, changed_by: str, reason: str | None) -> int:
    print(json.dumps(job_service.disable_maintenance_mode(changed_by=changed_by, reason=reason), indent=2))
    return 0


def run_control_plane_maintenance_workflow(
    *,
    output_path: str,
    changed_by: str,
    reason: str | None,
    allow_running_jobs: bool,
    keep_maintenance_enabled: bool,
) -> int:
    summary = control_plane_maintenance_service.execute_workflow(
        output_path=output_path,
        changed_by=changed_by,
        reason=reason,
        allow_running_jobs=allow_running_jobs,
        disable_maintenance_on_success=not keep_maintenance_enabled,
    )
    print(json.dumps(summary.to_dict(), indent=2))
    return 0


def run_prepare_control_plane_cutover_bundle(
    *,
    output_path: str,
    target_database_url: str,
    changed_by: str,
    reason: str | None,
    allow_running_jobs: bool,
    keep_maintenance_enabled: bool,
) -> int:
    summary = control_plane_cutover_service.prepare_cutover_bundle(
        output_path=output_path,
        target_database_url=target_database_url,
        changed_by=changed_by,
        reason=reason,
        allow_running_jobs=allow_running_jobs,
        disable_maintenance_on_success=not keep_maintenance_enabled,
    )
    print(json.dumps(summary.to_dict(), indent=2))
    return 0


def run_emit_control_plane_alerts(*, force: bool) -> int:
    alerts = job_service.emit_control_plane_alerts(force=force)
    payload = {
        "emitted_count": len(alerts),
        "alerts": [record.to_dict() for record in alerts],
    }
    print(json.dumps(payload, indent=2))
    return 0


def run_process_control_plane_alert_followups(*, force: bool) -> int:
    alerts = job_service.process_control_plane_alert_follow_ups(force=force)
    payload = {
        "emitted_count": len(alerts),
        "alerts": [record.to_dict() for record in alerts],
    }
    print(json.dumps(payload, indent=2))
    return 0


def run_list_control_plane_alerts(*, limit: int) -> int:
    print(json.dumps([record.to_dict() for record in job_service.list_control_plane_alerts(limit)], indent=2))
    return 0


def run_acknowledge_control_plane_alert(*, alert_id: str, acknowledged_by: str, acknowledgement_note: str | None) -> int:
    record = job_service.acknowledge_control_plane_alert(
        alert_id=alert_id,
        acknowledged_by=acknowledged_by,
        acknowledgement_note=acknowledgement_note,
    )
    print(json.dumps(record.to_dict(), indent=2))
    return 0


def run_create_control_plane_alert_silence(
    *,
    created_by: str,
    reason: str,
    duration_minutes: int,
    match_alert_key: str | None,
    match_finding_code: str | None,
) -> int:
    record = job_service.create_control_plane_alert_silence(
        created_by=created_by,
        reason=reason,
        duration_minutes=duration_minutes,
        match_alert_key=match_alert_key,
        match_finding_code=match_finding_code,
    )
    print(json.dumps(record.to_dict(), indent=2))
    return 0


def run_list_control_plane_alert_silences(*, active_only: bool) -> int:
    print(
        json.dumps(
            [record.to_dict() for record in job_service.list_control_plane_alert_silences(active_only=active_only)],
            indent=2,
        )
    )
    return 0


def run_cancel_control_plane_alert_silence(*, silence_id: str, cancelled_by: str) -> int:
    record = job_service.cancel_control_plane_alert_silence(
        silence_id=silence_id,
        cancelled_by=cancelled_by,
    )
    print(json.dumps(record.to_dict(), indent=2))
    return 0


def run_create_control_plane_oncall_schedule(
    *,
    created_by: str,
    environment_name: str | None,
    created_by_team: str | None,
    created_by_role: str | None,
    change_reason: str | None,
    approved_by: str | None,
    approved_by_team: str | None,
    approved_by_role: str | None,
    approval_note: str | None,
    team_name: str,
    timezone_name: str,
    weekdays: list[int],
    start_time: str,
    end_time: str,
    priority: int,
    rotation_name: str | None,
    effective_start_date: str | None,
    effective_end_date: str | None,
    webhook_url: str | None,
    escalation_webhook_url: str | None,
) -> int:
    record = control_plane_alert_service.create_oncall_schedule(
        created_by=created_by,
        environment_name=environment_name,
        created_by_team=created_by_team,
        created_by_role=created_by_role,
        change_reason=change_reason,
        approved_by=approved_by,
        approved_by_team=approved_by_team,
        approved_by_role=approved_by_role,
        approval_note=approval_note,
        team_name=team_name,
        timezone_name=timezone_name,
        weekdays=weekdays,
        start_time=start_time,
        end_time=end_time,
        priority=priority,
        rotation_name=rotation_name,
        effective_start_date=effective_start_date,
        effective_end_date=effective_end_date,
        webhook_url=webhook_url,
        escalation_webhook_url=escalation_webhook_url,
    )
    print(json.dumps(record.to_dict(), indent=2))
    return 0


def run_submit_control_plane_oncall_change_request(
    *,
    created_by: str,
    environment_name: str | None,
    created_by_team: str | None,
    created_by_role: str | None,
    change_reason: str,
    team_name: str,
    timezone_name: str,
    weekdays: list[int],
    start_time: str,
    end_time: str,
    priority: int,
    rotation_name: str | None,
    effective_start_date: str | None,
    effective_end_date: str | None,
    webhook_url: str | None,
    escalation_webhook_url: str | None,
) -> int:
    record = control_plane_alert_service.submit_oncall_change_request(
        created_by=created_by,
        environment_name=environment_name,
        created_by_team=created_by_team,
        created_by_role=created_by_role,
        change_reason=change_reason,
        team_name=team_name,
        timezone_name=timezone_name,
        weekdays=weekdays,
        start_time=start_time,
        end_time=end_time,
        priority=priority,
        rotation_name=rotation_name,
        effective_start_date=effective_start_date,
        effective_end_date=effective_end_date,
        webhook_url=webhook_url,
        escalation_webhook_url=escalation_webhook_url,
    )
    print(json.dumps(record.to_dict(), indent=2))
    return 0


def run_list_control_plane_oncall_change_requests(*, status: str | None) -> int:
    print(
        json.dumps(
            [record.to_dict() for record in control_plane_alert_service.list_oncall_change_requests(status=status)],
            indent=2,
        )
    )
    return 0


def run_review_control_plane_oncall_change_request(
    *,
    request_id: str,
    decision: str,
    reviewed_by: str,
    reviewed_by_team: str | None,
    reviewed_by_role: str | None,
    review_note: str | None,
) -> int:
    record = control_plane_alert_service.review_oncall_change_request(
        request_id=request_id,
        decision=decision,
        reviewed_by=reviewed_by,
        reviewed_by_team=reviewed_by_team,
        reviewed_by_role=reviewed_by_role,
        review_note=review_note,
    )
    print(json.dumps(record.to_dict(), indent=2))
    return 0


def run_assign_control_plane_oncall_change_request(
    *,
    request_id: str,
    assigned_to: str,
    assigned_to_team: str | None,
    assigned_by: str,
    assignment_note: str | None,
) -> int:
    record = control_plane_alert_service.assign_oncall_change_request(
        request_id=request_id,
        assigned_to=assigned_to,
        assigned_to_team=assigned_to_team,
        assigned_by=assigned_by,
        assignment_note=assignment_note,
    )
    print(json.dumps(record.to_dict(), indent=2))
    return 0


def run_list_control_plane_oncall_schedules(*, active_only: bool) -> int:
    print(
        json.dumps(
            [record.to_dict() for record in control_plane_alert_service.list_oncall_schedules(active_only=active_only)],
            indent=2,
        )
    )
    return 0


def run_resolve_control_plane_oncall_route(*, at: str | None) -> int:
    preview = control_plane_alert_service.preview_oncall_route(
        reference_timestamp=_parse_timestamp_argument(at),
    )
    print(json.dumps(preview, indent=2))
    return 0


def run_cancel_control_plane_oncall_schedule(*, schedule_id: str, cancelled_by: str) -> int:
    record = control_plane_alert_service.cancel_oncall_schedule(
        schedule_id=schedule_id,
        cancelled_by=cancelled_by,
    )
    print(json.dumps(record.to_dict(), indent=2))
    return 0


def _print_observation_result(result: ObservationResult) -> None:
    payload = {
        "command": result.command,
        "trace_path": result.trace_path,
        "trace_metadata_path": result.metadata_path,
        "trace_symbol_map_path": result.symbol_map_path,
        "trace_context_map_path": result.context_map_path,
        "line_count": result.line_count,
        "return_code": result.return_code,
    }
    print(json.dumps(payload, indent=2))


def _build_trace_collection_request(
    *,
    pid: int,
    program: str,
    output_path: str | None,
    duration: float | None,
    max_events: int | None,
    symbol_map_path: str | None,
) -> TraceCollectionRequest:
    program_path = Path(program)
    if program_path.suffix == ".bt":
        return TraceCollectionRequest(
            pid=pid,
            program_path=str(program_path),
            output_path=output_path,
            duration_seconds=duration,
            max_events=max_events,
            symbol_map_path=symbol_map_path,
        )
    return TraceCollectionRequest(
        pid=pid,
        program_path=str(program_path),
        output_path=output_path,
        duration_seconds=duration,
        max_events=max_events,
        command=["/bin/sh", str(program_path)],
        symbol_map_path=symbol_map_path,
    )


def _parse_timestamp_argument(raw_value: str | None) -> datetime | None:
    if raw_value is None:
        return None
    parsed = datetime.fromisoformat(raw_value)
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include a timezone offset.")
    return parsed


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "ingest":
        return run_ingest(
            args.repo_path,
            args.output_path,
            persist=not args.no_persist,
            snapshot_id=args.snapshot_id,
        )
    if args.command == "audit":
        if args.out_dir:
            Path(args.out_dir).mkdir(parents=True, exist_ok=True)
        return run_audit(
            args.snapshot_ref,
            args.events_path,
            snapshot_is_id=args.snapshot_id,
            out_dir=args.out_dir,
            persist=not args.no_persist,
            audit_id=args.audit_id,
        )
    if args.command == "audit-trace":
        if args.out_dir:
            Path(args.out_dir).mkdir(parents=True, exist_ok=True)
        return run_audit_trace(
            args.snapshot_ref,
            args.trace_path,
            snapshot_is_id=args.snapshot_id,
            trace_format=args.trace_format,
            out_dir=args.out_dir,
            persist=not args.no_persist,
            audit_id=args.audit_id,
        )
    if args.command == "collect-trace":
        return run_collect_trace(
            args.pid,
            args.program,
            output_path=args.out,
            duration=args.duration,
            max_events=args.max_events,
            symbol_map_path=args.symbol_map,
        )
    if args.command == "collect-audit":
        return run_collect_audit(
            args.snapshot_ref,
            args.pid,
            snapshot_is_id=args.snapshot_id,
            program=args.program,
            duration=args.duration,
            max_events=args.max_events,
            trace_format=args.trace_format,
            output_path=args.out,
            persist=not args.no_persist,
            audit_id=args.audit_id,
            symbol_map_path=args.symbol_map,
        )
    if args.command == "parse-trace":
        return run_parse_trace(args.trace_path, args.trace_format, args.out)
    if args.command == "worker":
        return run_worker(
            poll_interval=args.poll_interval,
            idle_timeout=args.idle_timeout,
            max_jobs=args.max_jobs,
            once=args.once,
        )
    if args.command == "list-snapshots":
        print(json.dumps([record.to_dict() for record in snapshot_repository.list()], indent=2))
        return 0
    if args.command == "list-audits":
        print(json.dumps([record.to_dict() for record in audit_repository.list()], indent=2))
        return 0
    if args.command == "list-remediation-reports":
        print(
            json.dumps(
                [
                    record.to_dict()
                    for record in remediation_index_service.list_reports(
                        limit=args.limit,
                        function=args.function,
                        risk=args.risk,
                        environment_name=args.environment_name,
                    )
                ],
                indent=2,
            )
        )
        return 0
    if args.command == "list-jobs":
        print(json.dumps([record.to_dict() for record in job_repository.list()], indent=2))
        return 0
    if args.command == "list-workers":
        print(json.dumps([record.to_dict() for record in job_repository.list_workers()], indent=2))
        return 0
    if args.command == "list-worker-heartbeats":
        print(json.dumps([record.to_dict() for record in job_repository.list_worker_heartbeats(args.worker_id)], indent=2))
        return 0
    if args.command == "list-worker-heartbeat-rollups":
        print(json.dumps([record.to_dict() for record in job_repository.list_worker_heartbeat_rollups(args.worker_id)], indent=2))
        return 0
    if args.command == "list-job-lease-events":
        print(json.dumps([record.to_dict() for record in job_repository.list_job_lease_events(args.job_id)], indent=2))
        return 0
    if args.command == "list-job-lease-event-rollups":
        print(json.dumps([record.to_dict() for record in job_repository.list_job_lease_event_rollups(args.job_id)], indent=2))
        return 0
    if args.command == "control-plane-analytics":
        return run_control_plane_analytics(days=args.days)
    if args.command == "control-plane-metrics":
        return run_control_plane_metrics(days=args.days)
    if args.command == "control-plane-maintenance-mode":
        return run_control_plane_maintenance_mode()
    if args.command == "control-plane-preflight":
        return run_control_plane_preflight()
    if args.command == "run-control-plane-runtime-smoke":
        return run_control_plane_runtime_smoke(
            changed_by=args.by,
            reason=args.reason,
            cleanup=not args.keep_artifacts,
        )
    if args.command == "run-control-plane-runtime-rehearsal":
        return run_control_plane_runtime_rehearsal(
            changed_by=args.by,
            expected_backend=args.expected_backend,
            reason=args.reason,
            cleanup=not args.keep_artifacts,
            ignore_deployment_readiness=args.ignore_deployment_readiness,
        )
    if args.command == "run-control-plane-backup-rehearsal":
        return run_control_plane_backup_rehearsal(
            changed_by=args.by,
            reason=args.reason,
            cleanup=not args.keep_artifacts,
        )
    if args.command == "run-control-plane-operational-validation":
        return run_control_plane_operational_validation(
            changed_by=args.by,
            expected_backend=args.expected_backend,
            reason=args.reason,
            process_backups=not args.skip_backup_processing,
            cleanup=not args.keep_artifacts,
            run_queue_validation=not args.skip_queue_validation,
            run_workload_validation=not args.skip_workload_validation,
            run_live_workload_drift_proof=not args.skip_live_workload_drift_proof,
            run_worker_recovery_validation=not args.skip_worker_recovery_validation,
            queue_success_jobs=args.queue_success_jobs,
            queue_failure_jobs=args.queue_failure_jobs,
            queue_delay_seconds=args.queue_delay_seconds,
            run_inline_queue_worker=not args.no_inline_queue_worker,
            workload_rounds=args.workload_rounds,
            workload_maintenance_pause_jobs=args.workload_maintenance_pause_jobs,
            inject_maintenance_mode_pause=not args.skip_maintenance_pause_injection,
        )
    if args.command == "run-control-plane-soak-validation":
        return run_control_plane_soak_validation(
            changed_by=args.by,
            expected_backend=args.expected_backend,
            reason=args.reason,
            target_profile_name=args.target_profile,
            iterations=args.iterations,
            pause_seconds=args.pause_seconds,
            process_backups=not args.skip_backup_processing,
            cleanup=not args.keep_artifacts,
            run_queue_validation=not args.skip_queue_validation,
            run_workload_validation=not args.skip_workload_validation,
            run_live_workload_drift_proof=not args.skip_live_workload_drift_proof,
            run_worker_recovery_validation=not args.skip_worker_recovery_validation,
            queue_success_jobs=args.queue_success_jobs,
            queue_failure_jobs=args.queue_failure_jobs,
            queue_delay_seconds=args.queue_delay_seconds,
            run_inline_queue_worker=not args.no_inline_queue_worker,
            workload_rounds=args.workload_rounds,
            workload_maintenance_pause_jobs=args.workload_maintenance_pause_jobs,
            inject_maintenance_mode_pause=not args.skip_maintenance_pause_injection,
        )
    if args.command == "run-control-plane-queue-validation":
        return run_control_plane_queue_validation(
            changed_by=args.by,
            reason=args.reason,
            queue_success_jobs=args.queue_success_jobs,
            queue_failure_jobs=args.queue_failure_jobs,
            queue_delay_seconds=args.queue_delay_seconds,
            run_inline_queue_worker=not args.no_inline_queue_worker,
        )
    if args.command == "run-live-workload-drift-proof":
        return run_live_workload_drift_proof(
            changed_by=args.by,
            reason=args.reason,
            persist=not args.no_persist,
            snapshot_id=args.snapshot_id,
            audit_id=args.audit_id,
        )
    if args.command == "control-plane-live-workload-target-validation":
        return run_control_plane_live_workload_target_validation()
    if args.command == "run-control-plane-live-workload-target-validation":
        return run_execute_control_plane_live_workload_target_validation(
            changed_by=args.by,
            reason=args.reason,
            timeout_seconds=args.timeout_seconds,
        )
    if args.command == "run-live-workload-target-profile-validation":
        return run_execute_live_workload_target_profile_validation(
            profile=args.profile,
            changed_by=args.by,
            reason=args.reason,
            timeout_seconds=args.timeout_seconds,
        )
    if args.command == "run-live-workload-target-profile-drift-proof":
        return run_live_workload_target_profile_drift_proof(
            profile=args.profile,
            changed_by=args.by,
            reason=args.reason,
            persist=not args.no_persist,
            snapshot_id=args.snapshot_id,
            audit_id=args.audit_id,
        )
    if args.command == "run-live-workload-target-profile-operational-validation":
        return run_live_workload_target_profile_operational_validation(
            profile=args.profile,
            changed_by=args.by,
            expected_backend=args.expected_backend,
            reason=args.reason,
            process_backups=not args.skip_backup_processing,
            cleanup=not args.no_cleanup,
            run_queue_validation=not args.skip_queue_validation,
            run_live_workload_drift_proof=not args.skip_live_workload_drift_proof,
            queue_success_jobs=args.queue_success_jobs,
            queue_failure_jobs=args.queue_failure_jobs,
            queue_delay_seconds=args.queue_delay_seconds,
            run_inline_queue_worker=not args.no_inline_queue_worker,
            run_workload_validation=not args.skip_workload_validation,
            workload_rounds=args.workload_rounds,
            workload_maintenance_pause_jobs=args.workload_maintenance_pause_jobs,
            inject_maintenance_mode_pause=not args.skip_maintenance_pause_injection,
            run_worker_recovery_validation=not args.skip_worker_recovery_validation,
        )
    if args.command == "run-live-workload-target-profile-canary-verify":
        return run_live_workload_target_profile_canary_verify(
            profile=args.profile,
            changed_by=args.by,
            expected_backend=args.expected_backend,
            reason=args.reason,
            process_backups=not args.skip_backup_processing,
            cleanup=not args.no_cleanup,
            run_queue_validation=not args.skip_queue_validation,
            run_workload_validation=not args.skip_workload_validation,
            run_worker_recovery_validation=not args.skip_worker_recovery_validation,
            queue_success_jobs=args.queue_success_jobs,
            queue_failure_jobs=args.queue_failure_jobs,
            queue_delay_seconds=args.queue_delay_seconds,
            run_inline_queue_worker=not args.no_inline_queue_worker,
            workload_rounds=args.workload_rounds,
            workload_maintenance_pause_jobs=args.workload_maintenance_pause_jobs,
            inject_maintenance_mode_pause=not args.skip_maintenance_pause_injection,
        )
    if args.command == "list-live-workload-target-profiles":
        return run_list_live_workload_target_profiles()
    if args.command == "export-live-workload-proof-bundle":
        return run_export_live_workload_proof_bundle(
            changed_by=args.by,
            reason=args.reason,
        )
    if args.command == "list-live-workload-proof-bundles":
        return run_list_live_workload_proof_bundles()
    if args.command == "inspect-live-workload-proof-bundle":
        return run_inspect_live_workload_proof_bundle(path=args.path)
    if args.command == "prune-live-workload-proof-bundles":
        return run_prune_live_workload_proof_bundles(
            changed_by=args.by,
            reason=args.reason,
            retention_days=args.retention_days,
        )
    if args.command == "delete-live-workload-proof-bundle":
        return run_delete_live_workload_proof_bundle(
            path=args.path,
            changed_by=args.by,
            reason=args.reason,
        )
    if args.command == "control-plane-runtime-validation":
        return run_control_plane_runtime_validation()
    if args.command == "control-plane-live-workload-proof-validation":
        return run_control_plane_live_workload_proof_validation()
    if args.command == "control-plane-backup-validation":
        return run_control_plane_backup_validation()
    if args.command == "control-plane-operational-validation-status":
        return run_control_plane_operational_validation_status()
    if args.command == "control-plane-soak-validation-status":
        return run_control_plane_soak_validation_status()
    if args.command == "control-plane-observability-export-validation":
        return run_control_plane_observability_export_validation()
    if args.command == "export-control-plane-observability":
        return run_control_plane_observability_export(
            changed_by=args.by,
            reason=args.reason,
        )
    if args.command == "list-control-plane-observability-exports":
        return run_list_control_plane_observability_exports()
    if args.command == "control-plane-backup-export-validation":
        return run_control_plane_backup_export_validation()
    if args.command == "list-control-plane-backups":
        return run_list_control_plane_backups()
    if args.command == "process-control-plane-backups":
        return run_process_control_plane_backups(
            changed_by=args.by,
            reason=args.reason,
            force=args.force,
        )
    if args.command == "control-plane-deployment-readiness":
        return run_control_plane_deployment_readiness()
    if args.command == "control-plane-trust-score":
        return run_control_plane_trust_score()
    if args.command == "control-plane-incident-narrative":
        return run_control_plane_incident_narrative()
    if args.command == "control-plane-deployment-readiness-owner-team-queue":
        return run_control_plane_deployment_readiness_owner_team_queue(
            status=args.status,
            owner_team=args.owner_team,
            assignment_state=args.assignment_state,
        )
    if args.command == "list-control-plane-runtime-validation-reviews":
        return run_list_control_plane_runtime_validation_reviews(
            status=args.status,
            owner_team=args.owner_team,
            assignment_state=args.assignment_state,
        )
    if args.command == "control-plane-runtime-validation-review-queue":
        return run_control_plane_runtime_validation_review_queue(
            status=args.status,
            owner_team=args.owner_team,
            assignment_state=args.assignment_state,
        )
    if args.command == "export-control-plane-runtime-validation-review-queue-csv":
        return run_export_control_plane_runtime_validation_review_queue_csv(
            status=args.status,
            owner_team=args.owner_team,
            assignment_state=args.assignment_state,
        )
    if args.command == "export-control-plane-deployment-readiness-owner-team-queue-csv":
        return run_export_control_plane_deployment_readiness_owner_team_queue_csv(
            status=args.status,
            owner_team=args.owner_team,
            assignment_state=args.assignment_state,
        )
    if args.command == "list-control-plane-runtime-validation-governance-requests":
        return run_list_control_plane_runtime_validation_governance_requests(
            status=args.status,
            owner_team=args.owner_team,
        )
    if args.command == "list-control-plane-runtime-validation-change-control-requests":
        return run_list_control_plane_runtime_validation_change_control_requests(
            status=args.status,
            owner_team=args.owner_team,
            assignment_state=getattr(args, "assignment_state", None),
        )
    if args.command == "process-control-plane-runtime-validation-reviews":
        return run_process_control_plane_runtime_validation_reviews(
            changed_by=args.by,
            reason=args.reason,
            force=args.force,
        )
    if args.command == "process-control-plane-runtime-validation-governance-requests":
        return run_process_control_plane_runtime_validation_governance_requests(
            changed_by=args.by,
            reason=args.reason,
            force=args.force,
        )
    if args.command == "process-control-plane-runtime-validation-change-control-requests":
        return run_process_control_plane_runtime_validation_change_control_requests(
            changed_by=args.by,
            reason=args.reason,
            force=args.force,
        )
    if args.command == "assign-control-plane-runtime-validation-change-control-request":
        return run_assign_control_plane_runtime_validation_change_control_request(
            request_id=args.request_id,
            assigned_to=args.assigned_to,
            assigned_to_team=args.assigned_team,
            assigned_by=args.by,
            assignment_note=args.note,
        )
    if args.command == "bulk-assign-control-plane-runtime-validation-change-control-requests":
        return run_bulk_assign_control_plane_runtime_validation_change_control_requests(
            assigned_to=args.assigned_to,
            assigned_to_team=args.assigned_team,
            assigned_by=args.by,
            assignment_note=args.note,
            status=args.status,
            owner_team=args.owner_team,
            assignment_state=args.assignment_state,
        )
    if args.command == "review-control-plane-runtime-validation-change-control-request":
        return run_review_control_plane_runtime_validation_change_control_request(
            request_id=args.request_id,
            decision=args.decision,
            decided_by=args.by,
            decision_note=args.note,
        )
    if args.command == "bulk-review-control-plane-runtime-validation-change-control-requests":
        return run_bulk_review_control_plane_runtime_validation_change_control_requests(
            decision=args.decision,
            decided_by=args.by,
            decision_note=args.note,
            status=args.status,
            owner_team=args.owner_team,
            assignment_state=args.assignment_state,
        )
    if args.command == "assign-control-plane-runtime-validation-review":
        return run_assign_control_plane_runtime_validation_review(
            review_id=args.review_id,
            assigned_to=args.assigned_to,
            assigned_to_team=args.assigned_team,
            assigned_by=args.by,
            assignment_note=args.note,
        )
    if args.command == "bulk-assign-control-plane-runtime-validation-reviews":
        return run_bulk_assign_control_plane_runtime_validation_reviews(
            assigned_to=args.assigned_to,
            assigned_to_team=args.assigned_team,
            assigned_by=args.by,
            assignment_note=args.note,
            status=args.status,
            owner_team=args.owner_team,
            assignment_state=args.assignment_state,
        )
    if args.command == "resolve-control-plane-runtime-validation-review":
        return run_resolve_control_plane_runtime_validation_review(
            review_id=args.review_id,
            resolved_by=args.by,
            resolution_reason=args.reason,
            resolution_note=args.note,
        )
    if args.command == "bulk-resolve-control-plane-runtime-validation-reviews":
        return run_bulk_resolve_control_plane_runtime_validation_reviews(
            resolved_by=args.by,
            resolution_reason=args.reason,
            resolution_note=args.note,
            status=args.status,
            owner_team=args.owner_team,
            assignment_state=args.assignment_state,
        )
    if args.command == "control-plane-runtime-backend":
        return run_control_plane_runtime_backend()
    if args.command == "inspect-control-plane-runtime-backend":
        return run_inspect_control_plane_runtime_backend(database_url=args.database_url)
    if args.command == "sync-postgres-runtime-shadow":
        return run_sync_postgres_runtime_shadow(
            target_database_url=args.target_database_url,
            changed_by=args.by,
            reason=args.reason,
        )
    if args.command == "control-plane-cutover-preflight":
        return run_control_plane_cutover_preflight(target_database_url=args.target_database_url)
    if args.command == "inspect-postgres-bootstrap-package":
        return run_inspect_postgres_bootstrap_package(package_dir=args.package_dir)
    if args.command == "inspect-postgres-target":
        return run_inspect_postgres_target(
            target_database_url=args.target_database_url,
            psql_executable=args.psql_executable,
        )
    if args.command == "plan-postgres-bootstrap-execution":
        return run_plan_postgres_bootstrap_execution(
            package_dir=args.package_dir,
            target_database_url=args.target_database_url,
            artifact_target_root=args.artifact_target_root,
            psql_executable=args.psql_executable,
        )
    if args.command == "execute-postgres-bootstrap-package":
        return run_execute_postgres_bootstrap_package(
            package_dir=args.package_dir,
            target_database_url=args.target_database_url,
            artifact_target_root=args.artifact_target_root,
            psql_executable=args.psql_executable,
            dry_run=args.dry_run,
        )
    if args.command == "verify-postgres-bootstrap-package":
        return run_verify_postgres_bootstrap_package(
            package_dir=args.package_dir,
            target_database_url=args.target_database_url,
            psql_executable=args.psql_executable,
        )
    if args.command == "run-postgres-cutover-rehearsal":
        return run_postgres_cutover_rehearsal(
            package_dir=args.package_dir,
            target_database_url=args.target_database_url,
            changed_by=args.by,
            reason=args.reason,
            psql_executable=args.psql_executable,
            artifact_target_root=args.artifact_target_root,
            apply_to_target=args.apply_to_target,
        )
    if args.command == "evaluate-control-plane-cutover-readiness":
        return run_evaluate_control_plane_cutover_readiness(
            package_dir=args.package_dir,
            target_database_url=args.target_database_url,
            rehearsal_max_age_hours=args.rehearsal_max_age_hours,
            require_apply_rehearsal=args.require_apply_rehearsal,
            require_runtime_validation=None if not args.skip_runtime_validation else False,
            require_live_workload_target_validation=(
                None if not args.skip_live_workload_target_validation else False
            ),
            require_live_workload_proof_validation=(
                None if not args.skip_live_workload_proof_validation else False
            ),
            require_backup_validation=None if not args.skip_backup_validation else False,
        )
    if args.command == "decide-control-plane-cutover":
        return run_decide_control_plane_cutover(
            package_dir=args.package_dir,
            target_database_url=args.target_database_url,
            changed_by=args.by,
            requested_decision=args.decision,
            reason=args.reason,
            decision_note=args.note,
            rehearsal_max_age_hours=args.rehearsal_max_age_hours,
            require_apply_rehearsal=args.require_apply_rehearsal,
            require_runtime_validation=None if not args.skip_runtime_validation else False,
            require_live_workload_target_validation=(
                None if not args.skip_live_workload_target_validation else False
            ),
            require_live_workload_proof_validation=(
                None if not args.skip_live_workload_proof_validation else False
            ),
            require_backup_validation=None if not args.skip_backup_validation else False,
            allow_override=args.allow_override,
        )
    if args.command == "list-control-plane-maintenance-events":
        return run_list_control_plane_maintenance_events(limit=args.limit)
    if args.command == "enable-control-plane-maintenance-mode":
        return run_enable_control_plane_maintenance_mode(changed_by=args.by, reason=args.reason)
    if args.command == "disable-control-plane-maintenance-mode":
        return run_disable_control_plane_maintenance_mode(changed_by=args.by, reason=args.reason)
    if args.command == "run-control-plane-maintenance-workflow":
        return run_control_plane_maintenance_workflow(
            output_path=args.out,
            changed_by=args.by,
            reason=args.reason,
            allow_running_jobs=args.allow_running_jobs,
            keep_maintenance_enabled=args.keep_maintenance_enabled,
        )
    if args.command == "prepare-control-plane-cutover-bundle":
        return run_prepare_control_plane_cutover_bundle(
            output_path=args.out,
            target_database_url=args.target_database_url,
            changed_by=args.by,
            reason=args.reason,
            allow_running_jobs=args.allow_running_jobs,
            keep_maintenance_enabled=args.keep_maintenance_enabled,
        )
    if args.command == "emit-control-plane-alerts":
        return run_emit_control_plane_alerts(force=args.force)
    if args.command == "process-control-plane-alert-followups":
        return run_process_control_plane_alert_followups(force=args.force)
    if args.command == "list-control-plane-alerts":
        return run_list_control_plane_alerts(limit=args.limit)
    if args.command == "acknowledge-control-plane-alert":
        return run_acknowledge_control_plane_alert(
            alert_id=args.alert_id,
            acknowledged_by=args.by,
            acknowledgement_note=args.note,
        )
    if args.command == "create-control-plane-alert-silence":
        return run_create_control_plane_alert_silence(
            created_by=args.by,
            reason=args.reason,
            duration_minutes=args.duration_minutes,
            match_alert_key=args.alert_key,
            match_finding_code=args.finding_code,
        )
    if args.command == "list-control-plane-alert-silences":
        return run_list_control_plane_alert_silences(active_only=args.active_only)
    if args.command == "cancel-control-plane-alert-silence":
        return run_cancel_control_plane_alert_silence(
            silence_id=args.silence_id,
            cancelled_by=args.by,
        )
    if args.command == "create-control-plane-oncall-schedule":
        return run_create_control_plane_oncall_schedule(
            created_by=args.by,
            environment_name=args.environment,
            created_by_team=args.creator_team,
            created_by_role=args.creator_role,
            change_reason=args.change_reason,
            approved_by=args.approved_by,
            approved_by_team=args.approver_team,
            approved_by_role=args.approver_role,
            approval_note=args.approval_note,
            team_name=args.team,
            timezone_name=args.timezone,
            weekdays=args.weekdays,
            start_time=args.start_time,
            end_time=args.end_time,
            priority=args.priority,
            rotation_name=args.rotation,
            effective_start_date=args.effective_start_date,
            effective_end_date=args.effective_end_date,
            webhook_url=args.webhook_url,
            escalation_webhook_url=args.escalation_webhook_url,
        )
    if args.command == "submit-control-plane-oncall-change-request":
        return run_submit_control_plane_oncall_change_request(
            created_by=args.by,
            environment_name=args.environment,
            created_by_team=args.creator_team,
            created_by_role=args.creator_role,
            change_reason=args.change_reason,
            team_name=args.team,
            timezone_name=args.timezone,
            weekdays=args.weekdays,
            start_time=args.start_time,
            end_time=args.end_time,
            priority=args.priority,
            rotation_name=args.rotation,
            effective_start_date=args.effective_start_date,
            effective_end_date=args.effective_end_date,
            webhook_url=args.webhook_url,
            escalation_webhook_url=args.escalation_webhook_url,
        )
    if args.command == "list-control-plane-oncall-change-requests":
        return run_list_control_plane_oncall_change_requests(status=args.status)
    if args.command == "review-control-plane-oncall-change-request":
        return run_review_control_plane_oncall_change_request(
            request_id=args.request_id,
            decision=args.decision,
            reviewed_by=args.by,
            reviewed_by_team=args.reviewer_team,
            reviewed_by_role=args.reviewer_role,
            review_note=args.note,
        )
    if args.command == "assign-control-plane-oncall-change-request":
        return run_assign_control_plane_oncall_change_request(
            request_id=args.request_id,
            assigned_to=args.assigned_to,
            assigned_to_team=args.assigned_team,
            assigned_by=args.by,
            assignment_note=args.note,
        )
    if args.command == "list-control-plane-oncall-schedules":
        return run_list_control_plane_oncall_schedules(active_only=args.active_only)
    if args.command == "resolve-control-plane-oncall-route":
        return run_resolve_control_plane_oncall_route(at=args.at)
    if args.command == "cancel-control-plane-oncall-schedule":
        return run_cancel_control_plane_oncall_schedule(
            schedule_id=args.schedule_id,
            cancelled_by=args.by,
        )
    if args.command == "control-plane-schema":
        return run_control_plane_schema()
    if args.command == "control-plane-schema-contract":
        return run_control_plane_schema_contract()
    if args.command == "migrate-control-plane-schema":
        return run_migrate_control_plane_schema()
    if args.command == "export-control-plane-backup":
        return run_export_control_plane_backup(output_path=args.out)
    if args.command == "import-control-plane-backup":
        return run_import_control_plane_backup(
            input_path=args.input_path,
            replace_existing=args.replace_existing,
        )
    if args.command == "prune-history":
        return run_prune_history()
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
