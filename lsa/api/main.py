from __future__ import annotations

import csv
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from io import StringIO
import json
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Header
from fastapi import Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from lsa.api.models import (
    AcknowledgeControlPlaneAlertRequest,
    AssignRuntimeValidationChangeControlRequest,
    AssignRuntimeValidationReviewRequest,
    AssignControlPlaneOnCallChangeRequest,
    AuditRecordPayload,
    AuditRequest,
    AuditResponse,
    AuditTraceRequest,
    CancelControlPlaneAlertSilenceRequest,
    CancelControlPlaneOnCallScheduleRequest,
    CollectAuditRequest,
    CollectAuditResponse,
    CollectTraceRequest,
    CollectTraceResponse,
    ControlPlaneBackupResponse,
    ControlPlaneBackupBundlePayload,
    ControlPlaneBackupExportValidationResponse,
    ControlPlaneBackupRehearsalResponse,
    ControlPlaneBackupValidationResponse,
    ControlPlaneAnalyticsResponse,
    ControlPlaneAlertRecordPayload,
    ControlPlaneAlertSilencePayload,
    ControlPlaneCanaryVerifierResponse,
    ControlPlaneCutoverPreflightResponse,
    ControlPlaneCutoverPromotionResponse,
    ControlPlaneCutoverReadinessResponse,
    ControlPlaneDeploymentReadinessResponse,
    ControlPlaneMaintenanceEventPayload,
    ControlPlaneIncidentNarrativeResponse,
    ControlPlaneMaintenancePreflightResponse,
    ControlPlaneOperationalValidationResponse,
    ControlPlaneOperationalValidationEvidenceResponse,
    ControlPlaneSoakValidationResponse,
    ControlPlaneSoakValidationEvidenceResponse,
    ControlPlaneObservabilityBundlePayload,
    ControlPlaneObservabilityExportResponse,
    ControlPlaneObservabilityExportValidationResponse,
    ControlPlaneQueueValidationResponse,
    ControlPlaneRuntimeRehearsalResponse,
    ControlPlaneOnCallChangeRequestPayload,
    ControlPlaneOnCallRouteResolutionPayload,
    ControlPlaneOnCallSchedulePayload,
    ControlPlaneMaintenanceModeResponse,
    ControlPlaneSchemaContractResponse,
    ControlPlaneSchemaStatusResponse,
    ControlPlaneRuntimeBackendResponse,
    ControlPlaneRuntimeSmokeResponse,
    ControlPlaneRuntimeValidationResponse,
    ControlPlaneTrustScoreResponse,
    ControlPlaneLiveWorkloadProofValidationResponse,
    ControlPlaneLiveWorkloadTargetValidationResponse,
    ControlPlaneRuntimeValidationReviewPayload,
    ControlPlaneRuntimeValidationReviewQueuePayload,
    ControlPlaneRuntimeValidationReviewBulkActionPayload,
    ControlPlaneRuntimeValidationGovernancePayload,
    ControlPlaneRuntimeValidationChangeControlPayload,
    ControlPlaneRuntimeValidationChangeControlQueuePayload,
    ControlPlaneRuntimeValidationChangeControlBulkActionPayload,
    ControlPlaneWorkerRecoveryValidationResponse,
    BulkAssignRuntimeValidationReviewsRequest,
    BulkResolveRuntimeValidationReviewsRequest,
    BulkAssignRuntimeValidationChangeControlRequest,
    BulkReviewRuntimeValidationChangeControlRequest,
    CreateControlPlaneAlertSilenceRequest,
    CreateControlPlaneOnCallChangeRequest,
    CreateOrganizationAssignmentCommentRequest,
    CreateControlPlaneOnCallScheduleRequest,
    DeleteLiveWorkloadProofBundleRequest,
    DeleteLiveWorkloadTargetProfileRequest,
    CreateOrganizationAssignmentRequest,
    BuildPostgresBootstrapExecutionPlanRequest,
    DecideControlPlaneCutoverRequest,
    EmitControlPlaneAlertsResponse,
    EvaluateControlPlaneCutoverReadinessRequest,
    ExecutePostgresBootstrapPackageRequest,
    ExecutePostgresBootstrapPackageResponse,
    ExportControlPlaneBackupRequest,
    ExportLiveWorkloadProofBundleRequest,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    ImportControlPlaneBackupRequest,
    InspectControlPlaneRuntimeBackendRequest,
    InspectLiveWorkloadProofBundleRequest,
    JobLeaseEventPayload,
    JobLeaseEventRollupPayload,
    JobRecordPayload,
    OrganizationAssignmentResponse,
    OrganizationAssignmentCommentResponse,
    OrganizationMembershipResponse,
    OrganizationProjectResponse,
    OrganizationRemovalEventResponse,
    OrganizationTeamResponse,
    OrganizationWorkspaceOperationsResponse,
    OrganizationWorkspaceResponse,
    LiveWorkloadProofBundleDeleteResponse,
    LiveWorkloadProofBundleInspectionResponse,
    LiveWorkloadProofBundlePruneResponse,
    LiveWorkloadProofBundleRecordResponse,
    LiveWorkloadProofBundleResponse,
    LiveWorkloadTargetProfileActivityAlertResponse,
    LiveWorkloadTargetProfileActivityEventResponse,
    LiveWorkloadTargetProfileActivityResponse,
    LiveWorkloadTargetProfileExplanationResponse,
    LiveWorkloadTargetProfileResponse,
    InspectPostgresTargetRequest,
    InspectPostgresBootstrapPackageRequest,
    PostgresBootstrapExecutionPlanResponse,
    PostgresBootstrapPackageInspectionResponse,
    PostgresCutoverRehearsalResponse,
    PostgresRuntimeShadowSyncResponse,
    PostgresTargetInspectionResponse,
    PrivilegedApiAuditEntryPayload,
    PrivilegedApiAuditAnalyticsPayload,
    ProcessRuntimeValidationChangeControlRequest,
    ProcessControlPlaneBackupsRequest,
    ProcessControlPlaneBackupsResponse,
    ProcessRuntimeValidationGovernanceRequest,
    ProcessRuntimeValidationReviewsRequest,
    PruneLiveWorkloadProofBundlesRequest,
    PruneHistoryResponse,
    PrunePrivilegedApiAuditResponse,
    PrepareControlPlaneCutoverBundleRequest,
    PrepareControlPlaneCutoverBundleResponse,
    RemediationIndexRecordPayload,
    ReviewControlPlaneOnCallChangeRequest,
    ReviewRuntimeValidationChangeControlRequest,
    ResolveRuntimeValidationReviewRequest,
    RunLiveWorkloadDriftProofRequest,
    RunLiveWorkloadTargetProfileCanaryVerifierRequest,
    RunLiveWorkloadTargetProfileDriftProofRequest,
    RunLiveWorkloadTargetProfileValidationRequest,
    RunLiveWorkloadTargetValidationRequest,
    RunPostgresCutoverRehearsalRequest,
    RunControlPlaneMaintenanceWorkflowRequest,
    RunControlPlaneMaintenanceWorkflowResponse,
    RunControlPlaneOperationalValidationRequest,
    RunControlPlaneSoakValidationRequest,
    RunControlPlaneQueueValidationRequest,
    RunControlPlaneRuntimeRehearsalRequest,
    RunControlPlaneRuntimeSmokeRequest,
    RunControlPlaneBackupRehearsalRequest,
    LiveWorkloadDriftProofResponse,
    ControlPlaneLiveWorkloadTargetValidationResponse,
    SetControlPlaneMaintenanceModeRequest,
    SnapshotRecordPayload,
    SyncPostgresRuntimeShadowRequest,
    SecretAliasResponse,
    UpsertSecretAliasRequest,
    DeleteSecretAliasRequest,
    DeleteSecretAliasResponse,
    UpdateOrganizationAssignmentRequest,
    RemoveOrganizationMembershipRequest,
    UpsertOrganizationMembershipRequest,
    UpsertOrganizationProjectRequest,
    UpsertOrganizationTeamRequest,
    UpsertLiveWorkloadTargetProfileRequest,
    VerifyPostgresBootstrapPackageRequest,
    VerifyPostgresBootstrapPackageResponse,
    WorkerHeartbeatPayload,
    WorkerHeartbeatRollupPayload,
    WorkerRecordPayload,
)
from lsa.core.intent_graph import IntentGraph
from lsa.core.models import FunctionIntent
from lsa.drift.comparator import DriftComparator
from lsa.drift.models import DriftAlert, ObservedEvent
from lsa.drift.trace_parser import load_trace_events
from lsa.remediation.llm_client import build_remediation_client, inspect_remediation_runtime
from lsa.remediation.prompt_builder import build_prompt
from lsa.services.audit_service import AuditService
from lsa.services.analytics_service import AnalyticsService, ControlPlaneAlertThresholds
from lsa.services.control_plane_alert_service import ControlPlaneAlertService
from lsa.services.control_plane_authorization_service import AuthorizedActor, ControlPlaneAuthorizationService
from lsa.services.control_plane_backup_service import ControlPlaneBackupService
from lsa.services.control_plane_backup_rehearsal_service import ControlPlaneBackupRehearsalService
from lsa.services.control_plane_backup_operations_service import ControlPlaneBackupOperationsService
from lsa.services.control_plane_backup_validation_service import ControlPlaneBackupValidationService
from lsa.services.control_plane_canary_verifier_service import ControlPlaneCanaryVerifierService
from lsa.services.control_plane_cutover_promotion_service import ControlPlaneCutoverPromotionService
from lsa.services.control_plane_cutover_service import ControlPlaneCutoverService
from lsa.services.control_plane_cutover_readiness_service import ControlPlaneCutoverReadinessService
from lsa.services.control_plane_live_workload_proof_validation_service import (
    ControlPlaneLiveWorkloadProofValidationService,
)
from lsa.services.control_plane_live_workload_target_validation_service import (
    ControlPlaneLiveWorkloadTargetValidationService,
)
from lsa.services.control_plane_incident_narrative_service import ControlPlaneIncidentNarrativeService
from lsa.services.control_plane_operational_validation_service import ControlPlaneOperationalValidationService
from lsa.services.control_plane_operational_validation_evidence_service import ControlPlaneOperationalValidationEvidenceService
from lsa.services.control_plane_soak_validation_service import ControlPlaneSoakValidationService
from lsa.services.control_plane_soak_validation_evidence_service import ControlPlaneSoakValidationEvidenceService
from lsa.services.control_plane_observability_export_service import ControlPlaneObservabilityExportService
from lsa.services.control_plane_queue_validation_service import ControlPlaneQueueValidationService
from lsa.services.control_plane_deployment_readiness_service import ControlPlaneDeploymentReadinessService
from lsa.services.control_plane_maintenance_service import ControlPlaneMaintenanceService
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
from lsa.services.metrics_service import ControlPlaneMetricsService
from lsa.services.organization_directory_service import OrganizationDirectoryService
from lsa.services.privileged_api_audit_service import PrivilegedApiAuditService
from lsa.services.live_workload_drift_proof_service import LiveWorkloadDriftProofService
from lsa.services.live_workload_proof_bundle_service import LiveWorkloadProofBundleService
from lsa.services.live_workload_target_profile_service import LiveWorkloadTargetProfile, LiveWorkloadTargetProfileService
from lsa.services.secret_reference_service import SecretReferenceService
from lsa.services.postgres_bootstrap_service import PostgresBootstrapService
from lsa.services.postgres_cutover_rehearsal_service import PostgresCutoverRehearsalService
from lsa.services.postgres_runtime_shadow_service import PostgresRuntimeShadowService
from lsa.services.postgres_target_service import PostgresTargetService
from lsa.services.remediation_index_service import RemediationIndexService
from lsa.services.oauth_identity_service import OAuthIdentityError, OAuthIdentityService
from lsa.services.runtime_validation_policy import RuntimeValidationPolicy, load_runtime_validation_policy_bundle
from lsa.services.trace_collection_service import TraceCollectionRequest, TraceCollectionService
from lsa.settings import (
    postgres_runtime_enabled,
    resolve_workspace_settings,
)
from lsa.storage.files import AuditRepository, JobRepository, SnapshotRepository, build_control_plane_runtime_bundle
from lsa.storage.database import inspect_database_runtime_support


settings = resolve_workspace_settings()
oauth_identity_service = (
    OAuthIdentityService(
        validation_url=str(settings.oauth_validation_url or "").strip(),
        timeout_seconds=settings.oauth_timeout_seconds,
    )
    if settings.oauth_enabled and settings.oauth_validation_url
    else None
)
organization_directory_service = OrganizationDirectoryService(
    path=settings.organization_directory_path,
    default_organization_name=settings.organization_name,
)
secret_reference_service = SecretReferenceService(settings.secret_aliases_path)
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
    worker_mode="embedded",
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
    worker_mode="embedded" if settings.run_embedded_worker else "external",
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
    worker_mode="embedded" if settings.run_embedded_worker else "external",
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


def _require_live_workload_target_profile(profile_name: str):
    profile = _live_workload_target_profile_service().resolve(profile_name)
    if profile is None:
        raise HTTPException(status_code=404, detail="Live workload target profile not found.")
    return profile


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


def _postgres_runtime_shadow_service() -> PostgresRuntimeShadowService:
    return PostgresRuntimeShadowService(
        settings=settings,
        source_job_repository=job_repository,
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.run_embedded_worker:
        job_service.start()
    try:
        yield
    finally:
        if settings.run_embedded_worker:
            job_service.stop()


app = FastAPI(title="Living Systems Auditor API", version="0.1.0", lifespan=lifespan)

if settings.api_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.api_allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

if settings.api_trusted_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.api_trusted_hosts))


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    if settings.api_security_headers_enabled:
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        )
    return response



OPS_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend" / "ops"


def _ops_frontend_html(filename: str) -> str:
    return (OPS_FRONTEND_DIR / filename).read_text()


app.mount("/ops-assets", StaticFiles(directory=OPS_FRONTEND_DIR / "assets"), name="ops-assets")


def _parse_timestamp_query(raw_value: str | None) -> datetime | None:
    if raw_value is None:
        return None
    try:
        parsed = datetime.fromisoformat(raw_value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Timestamp must use ISO 8601 format.") from exc
    if parsed.tzinfo is None:
        raise HTTPException(status_code=400, detail="Timestamp must include a timezone offset.")
    return parsed


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    active_workers = job_service.active_worker_count()
    database_status = job_repository.database_status()
    maintenance_mode = job_repository.maintenance_mode_status()
    remediation_status = inspect_remediation_runtime(settings)
    runtime_validation = _control_plane_runtime_validation_service().build_summary()
    live_workload_target_validation = _control_plane_live_workload_target_validation_service().build_summary()
    live_workload_proof_validation = _control_plane_live_workload_proof_validation_service().build_summary()
    operational_validation = _control_plane_operational_validation_evidence_service().build_summary()
    soak_validation = _control_plane_soak_validation_evidence_service().build_summary()
    backup_validation = _control_plane_backup_validation_service().build_summary()
    backup_export_validation = _control_plane_backup_operations_service().latest_backup_export_validation()
    observability_export_validation = control_plane_observability_export_service.latest_export_validation()
    deployment_readiness = _control_plane_deployment_readiness_service().evaluate()
    snapshot_backend = str(snapshot_repository.database.config.backend)
    audit_backend = str(audit_repository.database.config.backend)
    job_backend = str(job_repository.database.config.backend)
    return HealthResponse(
        status="ok",
        organization_name=settings.organization_name,
        environment_name=settings.environment_name,
        auth_enabled=settings.api_key is not None,
        authz_enabled=settings.authz_enabled,
        require_actor_headers=settings.require_actor_headers,
        require_actor_organization_headers=settings.require_actor_organization_headers,
        remediation_provider=remediation_status.provider,
        remediation_model=remediation_status.model,
        remediation_runtime_enabled=remediation_status.enabled,
        remediation_runtime_available=remediation_status.available,
        remediation_fallback_enabled=remediation_status.fallback_active,
        remediation_runtime_blockers=list(remediation_status.blockers),
        worker_mode="embedded" if settings.run_embedded_worker else "external",
        database_backend=str(database_status["backend"]),
        database_url=str(database_status["redacted_url"]),
        database_path=str(database_status["path"]),
        snapshot_repository_backend=snapshot_backend,
        audit_repository_backend=audit_backend,
        job_repository_backend=job_backend,
        postgres_runtime_enabled=postgres_runtime_enabled(settings),
        postgres_runtime_active=bool(
            postgres_runtime_enabled(settings)
            and snapshot_backend == "postgres"
            and audit_backend == "postgres"
            and job_repository.database.config.backend == "postgres"
        ),
        database_runtime_supported=bool(database_status["runtime_supported"]),
        database_runtime_driver=str(database_status["runtime_driver"]),
        database_runtime_dependency_installed=bool(database_status["runtime_dependency_installed"]),
        database_runtime_available=bool(database_status["runtime_available"]),
        database_runtime_blockers=[str(item) for item in database_status["runtime_blockers"]],
        database_ready=bool(database_status["ready"]),
        database_writable=bool(database_status["writable"]),
        database_schema_version=int(database_status["schema_version"]),
        database_expected_schema_version=int(database_status["expected_schema_version"]),
        database_schema_ready=bool(database_status["schema_ready"]),
        database_pending_migration_count=int(database_status["pending_migration_count"]),
        maintenance_mode_active=bool(maintenance_mode["active"]),
        worker_running=active_workers > 0 if not settings.run_embedded_worker else job_service.is_worker_running(),
        active_workers=active_workers,
        queued_jobs=job_service.count_jobs_by_status("queued"),
        running_jobs=job_service.count_jobs_by_status("running"),
        runtime_validation_status=runtime_validation.status,
        runtime_validation_cadence_status=runtime_validation.cadence_status,
        live_workload_target_status=live_workload_target_validation.status,
        live_workload_target_cadence_status=live_workload_target_validation.cadence_status,
        live_workload_proof_status=live_workload_proof_validation.status,
        live_workload_proof_cadence_status=live_workload_proof_validation.cadence_status,
        operational_validation_status=operational_validation.status,
        soak_validation_status=soak_validation.status,
        backup_validation_status=backup_validation.status,
        backup_validation_cadence_status=backup_validation.cadence_status,
        backup_export_validation_status=backup_export_validation.status,
        observability_export_validation_status=observability_export_validation.status,
        deployment_readiness_ready=deployment_readiness.ready,
        deployment_readiness_blocker_count=len(deployment_readiness.blockers),
        snapshots_dir=str(settings.snapshots_dir),
        audits_dir=str(settings.audits_dir),
        reports_dir=str(settings.reports_dir),
        traces_dir=str(settings.traces_dir),
    )


def require_api_key(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    if settings.api_key is None:
        return
    if x_api_key == settings.api_key:
        return
    if settings.oauth_enabled and authorization is not None and authorization.startswith("Bearer "):
        return
    if authorization is not None and authorization.startswith("Bearer "):
        if authorization[len("Bearer ") :].strip() == settings.api_key:
            return
    raise HTTPException(status_code=401, detail="Valid API key required.")


@dataclass(slots=True)
class ControlPlaneActor:
    actor_id: str
    role: str
    team: str | None
    organization: str | None
    auth_method: str
    oauth_apps: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, str | None]:
        return {
            "actor_id": self.actor_id,
            "role": self.role,
            "team": self.team,
            "organization": self.organization,
            "auth_method": self.auth_method,
            "oauth_apps": ",".join(self.oauth_apps),
        }


def require_authenticated_actor(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    x_actor_id: str | None = Header(default=None),
    x_actor_role: str | None = Header(default=None),
    x_actor_team: str | None = Header(default=None),
    x_actor_organization: str | None = Header(default=None),
) -> ControlPlaneActor:
    require_api_key(x_api_key=x_api_key, authorization=authorization)
    actor_team = (x_actor_team or "").strip() or None
    actor_organization = (x_actor_organization or "").strip().lower() or None
    if settings.oauth_enabled and oauth_identity_service is not None and not x_api_key:
        if authorization is None or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="OAuth bearer token required.")
    if (
        settings.oauth_enabled
        and oauth_identity_service is not None
        and authorization is not None
        and authorization.startswith("Bearer ")
        and (settings.api_key is None or authorization[len("Bearer ") :].strip() != settings.api_key)
    ):
        bearer_token = authorization[len("Bearer ") :].strip()
        try:
            identity = oauth_identity_service.validate_access_token(bearer_token)
        except OAuthIdentityError as error:
            raise HTTPException(status_code=401, detail=str(error)) from error
        membership = organization_directory_service.resolve_primary_membership(
            identity.username,
            actor_organization or settings.organization_name,
        )
        return ControlPlaneActor(
            actor_id=identity.username,
            role="admin" if identity.role == "admin" else "operator",
            team=actor_team or (membership.team_name if membership else None),
            organization=actor_organization or (membership.organization_name if membership else settings.organization_name),
            auth_method="oauth",
            oauth_apps=identity.apps,
        )

    actor_id = (x_actor_id or "").strip()
    actor_role = (x_actor_role or "").strip().lower()
    auth_method = "api_key" if x_api_key else "bearer" if authorization else "local"

    if settings.authz_enabled or settings.require_actor_headers:
        if not actor_id:
            raise HTTPException(status_code=400, detail="X-Actor-Id header required.")
        if not actor_role:
            raise HTTPException(status_code=400, detail="X-Actor-Role header required.")
    if settings.authz_enabled or settings.require_actor_organization_headers:
        if not actor_organization:
            raise HTTPException(status_code=400, detail="X-Actor-Organization header required.")

    if not actor_id:
        actor_id = "api"
    if not actor_role:
        actor_role = "admin"
    if not actor_organization:
        actor_organization = settings.organization_name

    return ControlPlaneActor(
        actor_id=actor_id,
        role=actor_role,
        team=actor_team,
        organization=actor_organization,
        auth_method=auth_method,
        oauth_apps=(),
    )


def require_operator_actor(actor: ControlPlaneActor = Depends(require_authenticated_actor)) -> ControlPlaneActor:
    if settings.authz_enabled and actor.role not in settings.authz_operator_roles:
        raise HTTPException(status_code=403, detail="Operator role required.")
    return actor


def require_admin_actor(actor: ControlPlaneActor = Depends(require_authenticated_actor)) -> ControlPlaneActor:
    if settings.authz_enabled and actor.role not in settings.authz_admin_roles:
        raise HTTPException(status_code=403, detail="Admin role required.")
    return actor


def _actor_is_admin(actor: ControlPlaneActor) -> bool:
    return actor.role in settings.authz_admin_roles


def _actor_has_oauth_feature(actor: ControlPlaneActor, *app_ids: str) -> bool:
    if actor.auth_method != "oauth" or _actor_is_admin(actor):
        return True
    normalized_actor_apps = {item.strip().lower() for item in actor.oauth_apps if item.strip()}
    normalized_required = {str(item or "").strip().lower() for item in app_ids if str(item or "").strip()}
    if not normalized_required:
        return True
    return not normalized_required.isdisjoint(normalized_actor_apps)


def _require_oauth_feature(actor: ControlPlaneActor, *app_ids: str) -> ControlPlaneActor:
    if not _actor_has_oauth_feature(actor, *app_ids):
        raise HTTPException(status_code=403, detail="OAuth session does not include the required app access.")
    return actor


def require_reports_actor(actor: ControlPlaneActor = Depends(require_operator_actor)) -> ControlPlaneActor:
    return _require_oauth_feature(actor, settings.oauth_reports_app_id)


def require_targets_actor(actor: ControlPlaneActor = Depends(require_operator_actor)) -> ControlPlaneActor:
    return _require_oauth_feature(actor, settings.oauth_targets_app_id)


def require_reviews_actor(actor: ControlPlaneActor = Depends(require_operator_actor)) -> ControlPlaneActor:
    return _require_oauth_feature(actor, settings.oauth_reviews_app_id)


def require_workspace_actor(actor: ControlPlaneActor = Depends(require_authenticated_actor)) -> ControlPlaneActor:
    _require_oauth_feature(actor, settings.oauth_platform_app_id)
    if _actor_is_admin(actor):
      return actor
    if organization_directory_service.user_has_management_access(
        actor.actor_id,
        actor.organization or settings.organization_name,
    ):
        return actor
    raise HTTPException(status_code=403, detail="Workspace manager or admin access required.")


def _normalized_team(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    return normalized or None


def _require_environment_scope(actor: ControlPlaneActor, environment_name: str | None) -> str:
    effective_environment = (environment_name or settings.environment_name).strip().lower() or settings.environment_name
    if settings.authz_enabled and not _actor_is_admin(actor) and effective_environment != settings.environment_name:
        raise HTTPException(status_code=403, detail="Actor is not authorized for this environment.")
    return effective_environment


def _require_team_scope(actor: ControlPlaneActor, *teams: str | None) -> str | None:
    scoped_teams = {_normalized_team(team) for team in teams if _normalized_team(team) is not None}
    if not settings.authz_enabled or _actor_is_admin(actor) or not scoped_teams:
        return next(iter(scoped_teams), None) if scoped_teams else _normalized_team(actor.team)
    actor_team = _normalized_team(actor.team)
    if actor_team is None:
        raise HTTPException(status_code=403, detail="Actor team required for team-scoped action.")
    if actor_team not in scoped_teams:
        raise HTTPException(status_code=403, detail="Actor team is not authorized for this target team.")
    return actor_team


def _scoped_owner_team(actor: ControlPlaneActor, owner_team: str | None) -> str | None:
    if not settings.authz_enabled or _actor_is_admin(actor):
        return _normalized_team(owner_team)
    actor_team = _normalized_team(actor.team)
    if actor_team is None:
        raise HTTPException(status_code=403, detail="Actor team required for owner-team scoped action.")
    if owner_team is None:
        return actor_team
    return _require_team_scope(actor, owner_team)


def _require_organization_scope(actor: ControlPlaneActor, organization_name: str | None) -> str:
    effective_organization = (organization_name or settings.organization_name).strip().lower() or settings.organization_name
    if settings.authz_enabled and not _actor_is_admin(actor):
        actor_organization = (actor.organization or settings.organization_name).strip().lower() or settings.organization_name
        if actor_organization != effective_organization:
            raise HTTPException(status_code=403, detail="Actor is not authorized for this organization.")
    return effective_organization


def _require_live_workload_target_profile_scope(actor: ControlPlaneActor, profile: LiveWorkloadTargetProfile) -> None:
    _require_organization_scope(actor, profile.organization_name)
    _require_environment_scope(actor, profile.environment_name or settings.environment_name)
    if profile.team_name:
        _require_team_scope(actor, profile.team_name)


def _actor_can_access_live_workload_target_profile(actor: ControlPlaneActor, profile: LiveWorkloadTargetProfile) -> bool:
    try:
        _require_live_workload_target_profile_scope(actor, profile)
    except HTTPException:
        return False
    return True


def _privileged_audit_details(actor: ControlPlaneActor, **details: object) -> dict[str, object]:
    payload = dict(details)
    payload["actor"] = actor.to_dict()
    payload["recorded_via"] = "api"
    return payload


def _maintenance_actor_details(actor: ControlPlaneActor) -> dict[str, object]:
    return {
        "actor_id": actor.actor_id,
        "role": actor.role,
        "team": actor.team,
        "organization": actor.organization,
        "auth_method": actor.auth_method,
        "recorded_via": "api",
    }


def _authorized_actor(actor: ControlPlaneActor) -> AuthorizedActor:
    return AuthorizedActor(
        actor_id=actor.actor_id,
        role=actor.role,
        team=actor.team,
        organization=actor.organization,
        auth_method=actor.auth_method,
    )


def _append_privileged_api_audit(
    *,
    actor: ControlPlaneActor,
    action: str,
    target: str,
    outcome: str,
    details: dict[str, object] | None = None,
) -> None:
    settings.privileged_api_audit_log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "recorded_at": datetime.now().astimezone().isoformat(),
        "environment_name": settings.environment_name,
        "action": action,
        "target": target,
        "outcome": outcome,
        "actor": actor.to_dict(),
        "details": details or {},
    }
    with settings.privileged_api_audit_log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def _read_privileged_api_audit(limit: int) -> list[dict[str, object]]:
    return list(
        reversed(
            PrivilegedApiAuditService(settings.privileged_api_audit_log_path).list_entries(limit=limit)
        )
    )


def require_control_plane_mutation_allowed() -> None:
    if job_repository.maintenance_mode_status()["active"]:
        raise HTTPException(status_code=503, detail="Control-plane maintenance mode is active.")


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
        raise HTTPException(status_code=500, detail="Runtime-validation review service is not configured.")
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


def _render_deployment_readiness_owner_team_queue_csv(
    *,
    status: str | None,
    owner_team: str | None,
    assignment_state: str | None,
) -> str:
    summary = job_service.runtime_validation_change_control_queue_summary(
        status=status,
        owner_team=owner_team,
        assignment_state=assignment_state,
    )
    if summary is None:
        raise HTTPException(status_code=500, detail="Runtime-validation review service is not configured.")
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
    return output.getvalue()


def _runtime_validation_review_queue_page() -> str:
    return _ops_frontend_html("runtime-validation-review-queue.html")


def _deployment_readiness_owner_team_queue_page() -> str:
    return _ops_frontend_html("deployment-readiness-owner-team-queue.html")


def _deployment_readiness_dashboard_page() -> str:
    return _ops_frontend_html("deployment-readiness-dashboard.html")


def _ops_home_page() -> str:
    return _ops_frontend_html("index.html")


@app.get("/metrics", response_class=PlainTextResponse, dependencies=[Depends(require_api_key)])
async def metrics(days: int = Query(default=1, ge=1, le=30)) -> PlainTextResponse:
    return PlainTextResponse(metrics_service.render_prometheus(days=days), media_type="text/plain; version=0.0.4")


@app.get(
    "/ops",
    response_class=HTMLResponse,
    dependencies=[Depends(require_api_key)],
)
async def ops_home_page() -> HTMLResponse:
    return HTMLResponse(_ops_home_page())


@app.get(
    "/ops/runtime-validation-review-queue",
    response_class=HTMLResponse,
    dependencies=[Depends(require_api_key)],
)
async def runtime_validation_review_queue_page() -> HTMLResponse:
    return HTMLResponse(_runtime_validation_review_queue_page())


@app.get(
    "/ops/deployment-readiness-owner-team-queue",
    response_class=HTMLResponse,
    dependencies=[Depends(require_api_key)],
)
async def deployment_readiness_owner_team_queue_page() -> HTMLResponse:
    return HTMLResponse(_deployment_readiness_owner_team_queue_page())


@app.get(
    "/ops/deployment-readiness-dashboard",
    response_class=HTMLResponse,
    dependencies=[Depends(require_api_key)],
)
async def deployment_readiness_dashboard_page() -> HTMLResponse:
    return HTMLResponse(_deployment_readiness_dashboard_page())


@app.get(
    "/maintenance/mode",
    response_model=ControlPlaneMaintenanceModeResponse,
    dependencies=[Depends(require_api_key)],
)
async def get_control_plane_maintenance_mode() -> ControlPlaneMaintenanceModeResponse:
    return ControlPlaneMaintenanceModeResponse(**job_repository.maintenance_mode_status())


@app.get(
    "/maintenance/control-plane-preflight",
    response_model=ControlPlaneMaintenancePreflightResponse,
    dependencies=[Depends(require_api_key)],
)
async def get_control_plane_preflight() -> ControlPlaneMaintenancePreflightResponse:
    return ControlPlaneMaintenancePreflightResponse(**control_plane_maintenance_service.build_preflight().to_dict())


@app.post(
    "/maintenance/control-plane-runtime-smoke",
    response_model=ControlPlaneRuntimeSmokeResponse,
    dependencies=[Depends(require_api_key)],
)
async def run_control_plane_runtime_smoke(
    request: RunControlPlaneRuntimeSmokeRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneRuntimeSmokeResponse:
    summary = _control_plane_runtime_smoke_service().run(
        changed_by=actor.actor_id,
        reason=request.reason,
        cleanup=request.cleanup,
        actor_details=_maintenance_actor_details(actor),
    )
    _append_privileged_api_audit(
        actor=actor,
        action="control-plane-runtime-smoke",
        target="control-plane-runtime",
        outcome=summary.smoke_id,
        details=_privileged_audit_details(actor, reason=request.reason),
    )
    return ControlPlaneRuntimeSmokeResponse(**summary.to_dict())


@app.post(
    "/maintenance/control-plane-runtime-rehearsal",
    response_model=ControlPlaneRuntimeRehearsalResponse,
    dependencies=[Depends(require_api_key)],
)
async def run_control_plane_runtime_rehearsal(
    request: RunControlPlaneRuntimeRehearsalRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneRuntimeRehearsalResponse:
    summary = _control_plane_runtime_rehearsal_service().run(
        changed_by=actor.actor_id,
        expected_backend=request.expected_backend,
        reason=request.reason,
        cleanup=request.cleanup,
        ignore_deployment_readiness=request.ignore_deployment_readiness,
        actor_details=_maintenance_actor_details(actor),
    )
    _append_privileged_api_audit(
        actor=actor,
        action="control-plane-runtime-rehearsal",
        target="control-plane-runtime",
        outcome=summary.status,
        details=_privileged_audit_details(
            actor,
            reason=request.reason,
            expected_backend=request.expected_backend,
            ignore_deployment_readiness=request.ignore_deployment_readiness,
        ),
    )
    return ControlPlaneRuntimeRehearsalResponse(**summary.to_dict())


@app.post(
    "/maintenance/control-plane-backup-rehearsal",
    response_model=ControlPlaneBackupRehearsalResponse,
    dependencies=[Depends(require_api_key)],
)
async def run_control_plane_backup_rehearsal(
    request: RunControlPlaneBackupRehearsalRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneBackupRehearsalResponse:
    summary = _control_plane_backup_rehearsal_service().run(
        changed_by=actor.actor_id,
        reason=request.reason,
        cleanup=request.cleanup,
        actor_details=_maintenance_actor_details(actor),
    )
    _append_privileged_api_audit(
        actor=actor,
        action="control-plane-backup-rehearsal",
        target="control-plane-backup",
        outcome=summary.status,
        details=_privileged_audit_details(actor, reason=request.reason),
    )
    return ControlPlaneBackupRehearsalResponse(**summary.to_dict())


@app.post(
    "/maintenance/control-plane-operational-validation",
    response_model=ControlPlaneOperationalValidationResponse,
    dependencies=[Depends(require_api_key)],
)
async def run_control_plane_operational_validation(
    request: RunControlPlaneOperationalValidationRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneOperationalValidationResponse:
    summary = _control_plane_operational_validation_service().run(
        changed_by=actor.actor_id,
        expected_backend=request.expected_backend,
        reason=request.reason,
        process_backups=request.process_backups,
        cleanup=request.cleanup,
        run_queue_validation=request.run_queue_validation,
        run_workload_validation=request.run_workload_validation,
        run_live_workload_drift_proof=request.run_live_workload_drift_proof,
        run_worker_recovery_validation=request.run_worker_recovery_validation,
        queue_success_jobs=request.queue_success_jobs,
        queue_failure_jobs=request.queue_failure_jobs,
        queue_delay_seconds=request.queue_delay_seconds,
        run_inline_queue_worker=request.run_inline_queue_worker,
        workload_rounds=request.workload_rounds,
        workload_maintenance_pause_jobs=request.workload_maintenance_pause_jobs,
        inject_maintenance_mode_pause=request.inject_maintenance_mode_pause,
        actor_details=_maintenance_actor_details(actor),
    )
    _append_privileged_api_audit(
        actor=actor,
        action="control-plane-operational-validation",
        target="control-plane",
        outcome=summary.status,
        details=_privileged_audit_details(
            actor,
            reason=request.reason,
            expected_backend=request.expected_backend,
            process_backups=request.process_backups,
        ),
    )
    return ControlPlaneOperationalValidationResponse(**summary.to_dict())


@app.post(
    "/maintenance/control-plane-soak-validation",
    response_model=ControlPlaneSoakValidationResponse,
    dependencies=[Depends(require_api_key)],
)
async def run_control_plane_soak_validation(
    request: RunControlPlaneSoakValidationRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneSoakValidationResponse:
    summary = _control_plane_soak_validation_service().run(
        changed_by=actor.actor_id,
        expected_backend=request.expected_backend,
        reason=request.reason,
        target_profile_name=request.target_profile_name,
        iterations=request.iterations,
        pause_seconds=request.pause_seconds,
        process_backups=request.process_backups,
        cleanup=request.cleanup,
        run_queue_validation=request.run_queue_validation,
        run_workload_validation=request.run_workload_validation,
        run_live_workload_drift_proof=request.run_live_workload_drift_proof,
        run_worker_recovery_validation=request.run_worker_recovery_validation,
        queue_success_jobs=request.queue_success_jobs,
        queue_failure_jobs=request.queue_failure_jobs,
        queue_delay_seconds=request.queue_delay_seconds,
        run_inline_queue_worker=request.run_inline_queue_worker,
        workload_rounds=request.workload_rounds,
        workload_maintenance_pause_jobs=request.workload_maintenance_pause_jobs,
        inject_maintenance_mode_pause=request.inject_maintenance_mode_pause,
        actor_details=_maintenance_actor_details(actor),
    )
    _append_privileged_api_audit(
        actor=actor,
        action="control-plane-soak-validation",
        target="control-plane",
        outcome=summary.status,
        details=_privileged_audit_details(
            actor,
            reason=request.reason,
            expected_backend=request.expected_backend,
            target_profile_name=request.target_profile_name,
            iterations=request.iterations,
            pause_seconds=request.pause_seconds,
        ),
    )
    return ControlPlaneSoakValidationResponse(**summary.to_dict())


@app.post(
    "/maintenance/control-plane-queue-validation",
    response_model=ControlPlaneQueueValidationResponse,
    dependencies=[Depends(require_api_key)],
)
async def run_control_plane_queue_validation(
    request: RunControlPlaneQueueValidationRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneQueueValidationResponse:
    summary = _control_plane_queue_validation_service().run(
        changed_by=actor.actor_id,
        reason=request.reason,
        success_jobs=request.queue_success_jobs,
        failure_jobs=request.queue_failure_jobs,
        delay_seconds=request.queue_delay_seconds,
        run_inline_worker=request.run_inline_queue_worker,
        actor_details=_maintenance_actor_details(actor),
    )
    _append_privileged_api_audit(
        actor=actor,
        action="control-plane-queue-validation",
        target="control-plane-queue",
        outcome=summary.status,
        details=_privileged_audit_details(
            actor,
            reason=request.reason,
            queue_success_jobs=request.queue_success_jobs,
            queue_failure_jobs=request.queue_failure_jobs,
        ),
    )
    return ControlPlaneQueueValidationResponse(**summary.to_dict())


@app.post(
    "/maintenance/live-workload-drift-proof",
    response_model=LiveWorkloadDriftProofResponse,
    dependencies=[Depends(require_api_key)],
)
async def run_live_workload_drift_proof(
    request: RunLiveWorkloadDriftProofRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> LiveWorkloadDriftProofResponse:
    summary = _live_workload_drift_proof_service().run(
        changed_by=actor.actor_id,
        reason=request.reason,
        persist=request.persist,
        snapshot_id=request.snapshot_id,
        audit_id=request.audit_id,
        actor_details=_maintenance_actor_details(actor),
    )
    _append_privileged_api_audit(
        actor=actor,
        action="live-workload-drift-proof",
        target="sample-service",
        outcome="passed" if summary.passed else "failed",
        details=_privileged_audit_details(
            actor,
            reason=request.reason,
            snapshot_id=summary.snapshot_id,
            audit_id=summary.audit_id,
            alert_count=summary.alert_count,
        ),
    )
    return LiveWorkloadDriftProofResponse(**summary.to_dict())


@app.get(
    "/maintenance/control-plane-runtime-validation",
    response_model=ControlPlaneRuntimeValidationResponse,
    dependencies=[Depends(require_api_key), Depends(require_reports_actor)],
)
async def get_control_plane_runtime_validation() -> ControlPlaneRuntimeValidationResponse:
    return ControlPlaneRuntimeValidationResponse(**_control_plane_runtime_validation_service().build_summary().to_dict())


@app.get(
    "/admin/organization-workspace",
    response_model=OrganizationWorkspaceResponse,
    dependencies=[Depends(require_api_key)],
)
async def get_organization_workspace(
    organization_name: str | None = Query(default=None),
    actor: ControlPlaneActor = Depends(require_workspace_actor),
) -> OrganizationWorkspaceResponse:
    _require_organization_scope(actor, organization_name or settings.organization_name)
    return _organization_workspace_response(organization_name or settings.organization_name)


@app.get(
    "/admin/organization-workspace/operations",
    response_model=OrganizationWorkspaceOperationsResponse,
    dependencies=[Depends(require_api_key)],
)
async def get_organization_workspace_operations(
    organization_name: str | None = Query(default=None),
    team_name: str | None = Query(default=None),
    project_name: str | None = Query(default=None),
    actor: ControlPlaneActor = Depends(require_workspace_actor),
) -> OrganizationWorkspaceOperationsResponse:
    return _organization_workspace_operations_response(
        actor,
        organization_name=organization_name or settings.organization_name,
        team_name=team_name,
        project_name=project_name,
    )


@app.get(
    "/admin/secret-aliases",
    response_model=list[SecretAliasResponse],
    dependencies=[Depends(require_api_key)],
)
async def list_secret_aliases(
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> list[SecretAliasResponse]:
    _ = actor
    return [SecretAliasResponse(**record.to_public_dict()) for record in secret_reference_service.list_aliases()]


@app.post(
    "/admin/secret-aliases",
    response_model=SecretAliasResponse,
    dependencies=[Depends(require_api_key)],
)
async def upsert_secret_alias(
    request: UpsertSecretAliasRequest,
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> SecretAliasResponse:
    try:
        record = secret_reference_service.upsert_alias(
            alias=request.alias,
            env_var_name=request.env_var_name,
            description=request.description,
            usage_scope=request.usage_scope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _append_privileged_api_audit(
        actor=actor,
        action="secret-alias-upsert",
        target=record.alias,
        outcome="ok",
        details=_privileged_audit_details(
            actor,
            env_var_name=record.env_var_name,
            usage_scope=record.usage_scope,
        ),
    )
    return SecretAliasResponse(**record.to_public_dict())


@app.post(
    "/admin/secret-aliases/delete",
    response_model=DeleteSecretAliasResponse,
    dependencies=[Depends(require_api_key)],
)
async def delete_secret_alias(
    request: DeleteSecretAliasRequest,
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> DeleteSecretAliasResponse:
    deleted = secret_reference_service.delete_alias(request.alias)
    _append_privileged_api_audit(
        actor=actor,
        action="secret-alias-delete",
        target=request.alias,
        outcome="ok" if deleted else "not_found",
        details=_privileged_audit_details(actor),
    )
    return DeleteSecretAliasResponse(alias=request.alias, deleted=deleted)


@app.post(
    "/admin/organization-workspace/teams",
    response_model=OrganizationTeamResponse,
    dependencies=[Depends(require_api_key)],
)
async def upsert_organization_team(
    request: UpsertOrganizationTeamRequest,
    actor: ControlPlaneActor = Depends(require_workspace_actor),
) -> OrganizationTeamResponse:
    organization_name = _require_organization_scope(actor, request.organization_name or settings.organization_name)
    team = organization_directory_service.upsert_team(
        organization_name=organization_name,
        team_name=request.team_name,
        description=request.description,
        manager_usernames=request.manager_usernames,
    )
    _append_privileged_api_audit(
        actor=actor,
        action="organization-team-upsert",
        target=team.team_name,
        outcome="ok",
        details=_privileged_audit_details(actor, organization_name=team.organization_name, manager_usernames=team.manager_usernames),
    )
    return OrganizationTeamResponse(**asdict(team))


@app.post(
    "/admin/organization-workspace/projects",
    response_model=OrganizationProjectResponse,
    dependencies=[Depends(require_api_key)],
)
async def upsert_organization_project(
    request: UpsertOrganizationProjectRequest,
    actor: ControlPlaneActor = Depends(require_workspace_actor),
) -> OrganizationProjectResponse:
    organization_name = _require_organization_scope(actor, request.organization_name or settings.organization_name)
    if request.team_name:
        _require_team_scope(actor, request.team_name)
    project = organization_directory_service.upsert_project(
        organization_name=organization_name,
        team_name=request.team_name,
        project_name=request.project_name,
        description=request.description,
    )
    _append_privileged_api_audit(
        actor=actor,
        action="organization-project-upsert",
        target=project.project_name,
        outcome="ok",
        details=_privileged_audit_details(actor, organization_name=project.organization_name, team_name=project.team_name),
    )
    return OrganizationProjectResponse(**asdict(project))


@app.post(
    "/admin/organization-workspace/memberships",
    response_model=OrganizationMembershipResponse,
    dependencies=[Depends(require_api_key)],
)
async def upsert_organization_membership(
    request: UpsertOrganizationMembershipRequest,
    actor: ControlPlaneActor = Depends(require_workspace_actor),
) -> OrganizationMembershipResponse:
    organization_name = _require_organization_scope(actor, request.organization_name or settings.organization_name)
    if request.team_name:
        _require_team_scope(actor, request.team_name)
    membership = organization_directory_service.upsert_membership(
        username=request.username,
        organization_name=organization_name,
        team_name=request.team_name,
        project_name=request.project_name,
        role=request.role,
        granted_by=actor.actor_id,
        note=request.note,
    )
    _append_privileged_api_audit(
        actor=actor,
        action="organization-membership-upsert",
        target=membership.username,
        outcome="ok",
        details=_privileged_audit_details(
            actor,
            organization_name=membership.organization_name,
            team_name=membership.team_name,
            project_name=membership.project_name,
            membership_role=membership.role,
            membership_status=membership.status,
        ),
    )
    return OrganizationMembershipResponse(**asdict(membership))


@app.post(
    "/admin/organization-workspace/memberships/{username}/remove",
    response_model=OrganizationRemovalEventResponse,
    dependencies=[Depends(require_api_key)],
)
async def remove_organization_membership(
    username: str,
    request: RemoveOrganizationMembershipRequest,
    actor: ControlPlaneActor = Depends(require_workspace_actor),
) -> OrganizationRemovalEventResponse:
    organization_name = _require_organization_scope(actor, request.organization_name or settings.organization_name)
    if request.team_name:
        _require_team_scope(actor, request.team_name)
    event = organization_directory_service.remove_membership(
        username=username,
        organization_name=organization_name,
        team_name=request.team_name,
        project_name=request.project_name,
        removed_by=actor.actor_id,
        reason=request.reason,
    )
    _append_privileged_api_audit(
        actor=actor,
        action="organization-membership-remove",
        target=event.username,
        outcome="ok",
        details=_privileged_audit_details(
            actor,
            organization_name=event.organization_name,
            team_name=event.team_name,
            project_name=event.project_name,
            removal_reason=event.reason,
        ),
    )
    return OrganizationRemovalEventResponse(**asdict(event))


@app.post(
    "/admin/organization-workspace/assignments",
    response_model=OrganizationAssignmentResponse,
    dependencies=[Depends(require_api_key)],
)
async def create_organization_assignment(
    request: CreateOrganizationAssignmentRequest,
    actor: ControlPlaneActor = Depends(require_workspace_actor),
) -> OrganizationAssignmentResponse:
    organization_name = _require_organization_scope(actor, request.organization_name or settings.organization_name)
    if request.team_name:
        _require_team_scope(actor, request.team_name)
    assignment = organization_directory_service.create_assignment(
        organization_name=organization_name,
        team_name=request.team_name,
        project_name=request.project_name,
        work_type=request.work_type,
        title=request.title,
        subject_id=request.subject_id,
        assigned_to=request.assigned_to,
        assigned_by=actor.actor_id,
        details=request.details,
    )
    _append_privileged_api_audit(
        actor=actor,
        action="organization-assignment-create",
        target=assignment.assignment_id,
        outcome="ok",
        details=_privileged_audit_details(
            actor,
            organization_name=assignment.organization_name,
            team_name=assignment.team_name,
            project_name=assignment.project_name,
            work_type=assignment.work_type,
            assigned_to=assignment.assigned_to,
            subject_id=assignment.subject_id,
        ),
    )
    return OrganizationAssignmentResponse(**asdict(assignment))


@app.post(
    "/admin/organization-workspace/assignments/{assignment_id}",
    response_model=OrganizationAssignmentResponse,
    dependencies=[Depends(require_api_key)],
)
async def update_organization_assignment(
    assignment_id: str,
    request: UpdateOrganizationAssignmentRequest,
    actor: ControlPlaneActor = Depends(require_workspace_actor),
) -> OrganizationAssignmentResponse:
    assignment = organization_directory_service.update_assignment(
        assignment_id=assignment_id,
        changed_by=actor.actor_id,
        status=request.status,
        assigned_to=request.assigned_to,
        title=request.title,
        details=request.details,
        comment=request.comment,
    )
    _append_privileged_api_audit(
        actor=actor,
        action="organization-assignment-update",
        target=assignment.assignment_id,
        outcome="ok",
        details=_privileged_audit_details(
            actor,
            organization_name=assignment.organization_name,
            team_name=assignment.team_name,
            project_name=assignment.project_name,
            status=assignment.status,
            assigned_to=assignment.assigned_to,
        ),
    )
    return OrganizationAssignmentResponse(**asdict(assignment))


@app.post(
    "/admin/organization-workspace/assignments/{assignment_id}/comments",
    response_model=OrganizationAssignmentCommentResponse,
    dependencies=[Depends(require_api_key)],
)
async def add_organization_assignment_comment(
    assignment_id: str,
    request: CreateOrganizationAssignmentCommentRequest,
    actor: ControlPlaneActor = Depends(require_workspace_actor),
) -> OrganizationAssignmentCommentResponse:
    comment = organization_directory_service.add_assignment_comment(
        assignment_id=assignment_id,
        author=actor.actor_id,
        body=request.body,
    )
    _append_privileged_api_audit(
        actor=actor,
        action="organization-assignment-comment",
        target=comment.assignment_id,
        outcome="ok",
        details=_privileged_audit_details(
            actor,
            organization_name=comment.organization_name,
            team_name=comment.team_name,
            project_name=comment.project_name,
            comment_kind=comment.kind,
        ),
    )
    return OrganizationAssignmentCommentResponse(**asdict(comment))


@app.get(
    "/maintenance/live-workload-target-profiles",
    response_model=list[LiveWorkloadTargetProfileResponse],
    dependencies=[Depends(require_api_key), Depends(require_targets_actor)],
)
async def list_live_workload_target_profiles(
    actor: ControlPlaneActor = Depends(require_targets_actor),
) -> list[LiveWorkloadTargetProfileResponse]:
    return [
        LiveWorkloadTargetProfileResponse(**profile.to_dict())
        for profile in _live_workload_target_profile_service().list_profiles()
        if _actor_can_access_live_workload_target_profile(actor, profile)
    ]


def _target_profile_matches_details(details: dict[str, object], profile_name: str) -> bool:
    if str(details.get("target_profile", "")).strip().lower() == profile_name:
        return True
    if str(details.get("target_profile_name", "")).strip().lower() == profile_name:
        return True
    for key in (
        "target_validation",
        "drift_proof",
        "live_workload_target_validation",
        "live_workload_drift_proof",
        "operational_validation",
        "runtime_rehearsal",
        "deployment_readiness",
    ):
        nested = details.get(key)
        if isinstance(nested, dict):
            if str(nested.get("target_profile", "")).strip().lower() == profile_name:
                return True
            if str(nested.get("target_profile_name", "")).strip().lower() == profile_name:
                return True
    return False


def _json_safe(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


def _target_activity_event_category(event_type: str) -> str:
    normalized = event_type.strip().lower()
    if "canary" in normalized:
        return "canary"
    if "target_validation" in normalized:
        return "target_validation"
    if "drift_proof" in normalized:
        return "drift_proof"
    if "operational_validation" in normalized:
        return "operational_validation"
    if "runtime" in normalized:
        return "runtime_validation"
    if "deployment_readiness" in normalized:
        return "deployment_readiness"
    if "backup" in normalized:
        return "backup"
    if "observability" in normalized:
        return "observability"
    return "other"


def _target_activity_alert_category(alert_key: str) -> str:
    normalized = alert_key.strip().lower()
    if "target-validation" in normalized or "target_validation" in normalized:
        return "target_validation"
    if "live-workload-proof" in normalized or "drift_proof" in normalized:
        return "drift_proof"
    if "operational" in normalized:
        return "operational_validation"
    if "deployment-readiness" in normalized or "deployment_readiness" in normalized:
        return "deployment_readiness"
    if "runtime" in normalized:
        return "runtime_validation"
    return "other"


def _normalize_risk_level(value: object, *, fallback: str = "MEDIUM") -> str:
    text = str(value or "").strip().upper()
    if text in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        return text
    if "CRITICAL" in text:
        return "CRITICAL"
    if "HIGH" in text:
        return "HIGH"
    if "MEDIUM" in text:
        return "MEDIUM"
    if "LOW" in text:
        return "LOW"
    return fallback


def _normalize_sentence(value: object, *, fallback: str, max_length: int = 420) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text:
        return fallback
    if len(text) > max_length:
        text = text[: max_length - 1].rstrip() + "…"
    return text


def _normalize_action_text(value: object, *, fallback: str, max_length: int = 520) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text:
        return fallback
    text = text.replace("**", "").replace("__", "").replace("`", "")
    for prefix in ("1. ", "2. ", "3. ", "4. ", "- ", "* "):
        while text.startswith(prefix):
            text = text[len(prefix):].lstrip()
    for numbered in (" 1. ", " 2. ", " 3. ", " 4. "):
        text = text.replace(numbered, " ")
    if len(text) > max_length:
        text = text[: max_length - 1].rstrip() + "…"
    return text


def _normalize_supporting_facts(facts: list[str], *, max_items: int = 6, max_length: int = 220) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for fact in facts:
        text = " ".join(str(fact or "").strip().split()).replace("**", "").replace("__", "").replace("`", "")
        if not text:
            continue
        if len(text) > max_length:
            text = text[: max_length - 1].rstrip() + "…"
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(text)
        if len(normalized) >= max_items:
            break
    return normalized


def _build_target_profile_activity(profile_name: str) -> LiveWorkloadTargetProfileActivityResponse:
    normalized = profile_name.strip().lower()
    profile = _require_live_workload_target_profile(normalized)
    latest_validation: dict[str, object] | None = None
    latest_drift_proof: dict[str, object] | None = None
    latest_canary_verification: dict[str, object] | None = None
    latest_operational_validation: dict[str, object] | None = None
    event_category_counts: dict[str, int] = {}
    alert_category_counts: dict[str, int] = {}
    recent_events: list[LiveWorkloadTargetProfileActivityEventResponse] = []
    recent_alerts: list[LiveWorkloadTargetProfileActivityAlertResponse] = []

    for record in job_service.list_control_plane_maintenance_events(limit=500):
        if not _target_profile_matches_details(record.details, normalized):
            continue
        category = _target_activity_event_category(record.event_type)
        event_category_counts[category] = event_category_counts.get(category, 0) + 1
        status = None
        summary = None
        if record.event_type == "live_workload_target_validation_executed":
            latest_validation = latest_validation or dict(_json_safe(record.details))
            status = str(record.details.get("status", "unknown"))
            summary = "Validation executed."
        elif record.event_type == "live_workload_drift_proof_executed":
            latest_drift_proof = latest_drift_proof or dict(_json_safe(record.details))
            status = "passed" if bool(record.details.get("passed")) else "failed"
            summary = "Drift proof executed."
        elif record.event_type == "control_plane_canary_verifier_executed":
            latest_canary_verification = latest_canary_verification or dict(_json_safe(record.details))
            status = str(record.details.get("verdict", "unknown"))
            summary = "Canary verifier executed."
        elif record.event_type == "control_plane_operational_validation_executed":
            latest_operational_validation = latest_operational_validation or dict(_json_safe(record.details))
            status = str(record.details.get("status", "unknown"))
            summary = "Operational validation executed."
        else:
            nested_status = record.details.get("status")
            status = None if nested_status is None else str(nested_status)
            summary = record.event_type.replace("_", " ")

        if len(recent_events) < 12:
            recent_events.append(
                LiveWorkloadTargetProfileActivityEventResponse(
                    event_id=record.event_id,
                    recorded_at=str(record.recorded_at),
                    event_type=record.event_type,
                    category=category,
                    changed_by=record.changed_by,
                    reason=record.reason,
                    status=status,
                    summary=summary,
                )
            )

    for record in job_service.list_control_plane_alerts(limit=200):
        payload = dict(record.payload or {})
        if not _target_profile_matches_details(payload, normalized):
            continue
        category = _target_activity_alert_category(record.alert_key)
        alert_category_counts[category] = alert_category_counts.get(category, 0) + 1
        if len(recent_alerts) >= 8:
            break
        recent_alerts.append(
            LiveWorkloadTargetProfileActivityAlertResponse(
                alert_id=record.alert_id,
                created_at=record.created_at,
                alert_key=record.alert_key,
                category=category,
                status=record.status,
                severity=record.severity,
                summary=record.summary,
            )
        )

    return LiveWorkloadTargetProfileActivityResponse(
        profile_name=normalized,
        organization_name=profile.organization_name,
        team_name=profile.team_name,
        project_name=profile.project_name,
        environment_name=profile.environment_name,
        latest_validation=latest_validation,
        latest_drift_proof=latest_drift_proof,
        latest_canary_verification=latest_canary_verification,
        latest_operational_validation=latest_operational_validation,
        event_category_counts=event_category_counts,
        alert_category_counts=alert_category_counts,
        recent_events=recent_events,
        recent_alerts=recent_alerts,
    )


def _extract_target_host(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "unknown-target"
    parsed = urlparse(raw)
    if parsed.netloc:
        return parsed.netloc
    if parsed.path:
        return parsed.path.split("/")[0]
    return raw


def _build_target_profile_explanation(profile_name: str) -> LiveWorkloadTargetProfileExplanationResponse:
    activity = _build_target_profile_activity(profile_name)
    profile = _require_live_workload_target_profile(profile_name)
    runtime = inspect_remediation_runtime(settings)
    generated_at = datetime.now().astimezone().isoformat()

    source_event_type = "healthy_target_profile"
    source_event_id: str | None = None
    status = "passed"
    risk = "LOW"
    summary = (
        f"Target profile '{profile.name}' is currently healthy. Validation, proof, and operational signals do not show an active failure."
    )
    immediate_action = "Keep cadence fresh and continue validating this profile after infrastructure or routing changes."
    long_term_fix = "No immediate fix required. Maintain explicit validation/proof URLs for production-like targets."
    supporting_facts = [
        f"Approved base URL: {profile.approved_base_url}",
        f"Drift base URL: {profile.drift_base_url}",
    ]

    source_details: dict[str, object] | None = None
    if activity.latest_operational_validation and str(activity.latest_operational_validation.get("status", "")).lower() != "passed":
        source_event_type = "control_plane_operational_validation_executed"
        source_event_id = str(activity.latest_operational_validation.get("validation_id") or activity.latest_operational_validation.get("event_id") or "")
        source_details = activity.latest_operational_validation
        status = str(activity.latest_operational_validation.get("status", "failed"))
        risk = "HIGH"
    elif activity.latest_drift_proof and not bool(activity.latest_drift_proof.get("passed")):
        source_event_type = "live_workload_drift_proof_executed"
        source_event_id = str(activity.latest_drift_proof.get("event_id") or "")
        source_details = activity.latest_drift_proof
        status = "failed"
        risk = "HIGH"
    elif activity.latest_validation and str(activity.latest_validation.get("status", "")).lower() != "passed":
        source_event_type = "live_workload_target_validation_executed"
        source_event_id = str(activity.latest_validation.get("latest_validation_event_id") or activity.latest_validation.get("event_id") or "")
        source_details = activity.latest_validation
        status = str(activity.latest_validation.get("status", "failed"))
        risk = "MEDIUM"

    if source_details is None:
        return LiveWorkloadTargetProfileExplanationResponse(
            profile_name=profile.name,
            status=status,
            source_event_type=source_event_type,
            source_event_id=source_event_id,
            generated_at=generated_at,
            remediation_provider=runtime.provider,
            remediation_model=runtime.model,
            remediation_available=runtime.available,
            remediation_fallback_active=runtime.fallback_active,
            title=f"Target profile '{profile.name}' is healthy",
            summary=summary,
            risk=risk,
            immediate_action=immediate_action,
            long_term_fix=long_term_fix,
            supporting_facts=supporting_facts,
        )

    observed_host = _extract_target_host(
        (
            source_details.get("drift_target_base_url")
            or source_details.get("drift_target_url")
            or source_details.get("approved_target_base_url")
            or profile.drift_base_url
        )
    )
    expected_host = _extract_target_host(profile.approved_probe_url or profile.approved_base_url)
    reason = str(source_details.get("reason") or source_event_type.replace("_", " "))
    alert = DriftAlert(
        function=f"target-profile:{profile.name}",
        observed_target=observed_host,
        expected_targets=[expected_host],
        severity=risk.lower(),
        reason=reason,
    )
    function = FunctionIntent(
        name=profile.name,
        module="live_workload_targets",
        qualname=f"target-profile:{profile.name}",
        lineno=0,
        end_lineno=0,
        intent_summary=(
            "Validate reachability and drift-proof behavior between approved and drift target destinations."
        ),
        invariants=[
            "Approved validation target should stay reachable.",
            "Drift proof should preserve explicit destination separation between approved and drift targets.",
            "Operational validation should complete without introducing readiness blockers.",
        ],
        external_hosts=[expected_host],
    )
    prompt = (
        build_prompt(function, alert)
        + "\nAdditional context:\n"
        + f"- Profile name: {profile.name}\n"
        + f"- Approved base URL: {profile.approved_base_url}\n"
        + f"- Drift base URL: {profile.drift_base_url}\n"
        + f"- Failure source event: {source_event_type}\n"
        + f"- Failure payload: {json.dumps(_json_safe(source_details), sort_keys=True)}\n"
        + "Explain the target failure in operator language and suggest the next verification step."
    )
    report = audit_service.remediation_client.analyze(function, alert, prompt, session=None)
    filtered_risk = _normalize_risk_level(report.risk, fallback=risk)
    filtered_summary = _normalize_sentence(
        report.summary,
        fallback=(
            f"Target profile '{profile.name}' failed during {source_event_type.replace('_', ' ')} and needs review."
        ),
    )
    filtered_immediate_action = _normalize_action_text(
        report.immediate_action,
        fallback="Confirm whether this failing target behavior is expected, then inspect the configured validation and proof URLs.",
    )
    filtered_long_term_fix = _normalize_action_text(
        report.long_term_fix,
        fallback="Keep explicit target routes documented and align alert severity with whether the target is intentionally failing or production-critical.",
    )
    filtered_facts = _normalize_supporting_facts(
        report.supporting_facts
        + [
            f"Profile name: {profile.name}",
            f"Approved base URL: {profile.approved_base_url}",
            f"Drift base URL: {profile.drift_base_url}",
            f"Failure source event: {source_event_type}",
        ]
    )
    return LiveWorkloadTargetProfileExplanationResponse(
        profile_name=profile.name,
        status=status,
        source_event_type=source_event_type,
        source_event_id=source_event_id or None,
        generated_at=generated_at,
        remediation_provider=runtime.provider,
        remediation_model=runtime.model,
        remediation_available=runtime.available,
        remediation_fallback_active=runtime.fallback_active,
        title=report.title,
        summary=filtered_summary,
        risk=filtered_risk,
        immediate_action=filtered_immediate_action,
        long_term_fix=filtered_long_term_fix,
        supporting_facts=filtered_facts,
    )


def _organization_workspace_response(organization_name: str | None = None) -> OrganizationWorkspaceResponse:
    snapshot = organization_directory_service.snapshot(organization_name)
    return OrganizationWorkspaceResponse(
        organization_name=snapshot.organization_name,
        teams=[OrganizationTeamResponse(**asdict(item)) for item in snapshot.teams],
        projects=[OrganizationProjectResponse(**asdict(item)) for item in snapshot.projects],
        memberships=[OrganizationMembershipResponse(**asdict(item)) for item in snapshot.memberships],
        removal_events=[OrganizationRemovalEventResponse(**asdict(item)) for item in snapshot.removal_events],
        assignments=[OrganizationAssignmentResponse(**asdict(item)) for item in snapshot.assignments],
        assignment_comments=[OrganizationAssignmentCommentResponse(**asdict(item)) for item in snapshot.assignment_comments],
    )


def _organization_workspace_operations_response(
    actor: ControlPlaneActor,
    *,
    organization_name: str | None = None,
    team_name: str | None = None,
    project_name: str | None = None,
) -> OrganizationWorkspaceOperationsResponse:
    effective_organization = _require_organization_scope(actor, organization_name or settings.organization_name)
    scoped_team = _normalized_team(team_name)
    scoped_project = (project_name or "").strip().lower() or None
    if scoped_team:
        _require_team_scope(actor, scoped_team)

    target_profiles: list[LiveWorkloadTargetProfileResponse] = []
    scoped_profile_names: set[str] = set()
    for profile in _live_workload_target_profile_service().list_profiles():
        if not _actor_can_access_live_workload_target_profile(actor, profile):
            continue
        profile_organization = (profile.organization_name or settings.organization_name).strip().lower() or settings.organization_name
        if profile_organization != effective_organization:
            continue
        if scoped_team and (profile.team_name or "").strip().lower() != scoped_team:
            continue
        if scoped_project and (profile.project_name or "").strip().lower() != scoped_project:
            continue
        target_profiles.append(LiveWorkloadTargetProfileResponse(**profile.to_dict()))
        scoped_profile_names.add(profile.name.strip().lower())

    soak_events: list[ControlPlaneMaintenanceEventPayload] = []
    require_profile_match = bool(scoped_team or scoped_project)
    for record in job_service.list_control_plane_maintenance_events(limit=250):
        if not record.event_type.startswith("control_plane_soak_validation_"):
            continue
        details = dict(record.details or {})
        profile_name = str(details.get("target_profile_name") or details.get("target_profile") or "").strip().lower()
        if require_profile_match and (not profile_name or profile_name not in scoped_profile_names):
            continue
        if scoped_profile_names and profile_name and profile_name not in scoped_profile_names:
            continue
        soak_events.append(ControlPlaneMaintenanceEventPayload(**record.to_dict()))
        if len(soak_events) >= 60:
            break

    return OrganizationWorkspaceOperationsResponse(
        organization_name=effective_organization,
        team_name=scoped_team,
        project_name=scoped_project,
        target_profiles=target_profiles,
        soak_events=soak_events,
    )


@app.get(
    "/maintenance/live-workload-target-profiles/{profile_name}/activity",
    response_model=LiveWorkloadTargetProfileActivityResponse,
    dependencies=[Depends(require_api_key)],
)
async def get_live_workload_target_profile_activity(
    profile_name: str,
    actor: ControlPlaneActor = Depends(require_targets_actor),
) -> LiveWorkloadTargetProfileActivityResponse:
    profile = _require_live_workload_target_profile(profile_name)
    _require_live_workload_target_profile_scope(actor, profile)
    return _build_target_profile_activity(profile.name)


@app.get(
    "/maintenance/live-workload-target-profiles/{profile_name}/explanation",
    response_model=LiveWorkloadTargetProfileExplanationResponse,
    dependencies=[Depends(require_api_key)],
)
async def get_live_workload_target_profile_explanation(
    profile_name: str,
    actor: ControlPlaneActor = Depends(require_targets_actor),
) -> LiveWorkloadTargetProfileExplanationResponse:
    profile = _require_live_workload_target_profile(profile_name)
    _require_live_workload_target_profile_scope(actor, profile)
    return _build_target_profile_explanation(profile.name)


@app.post(
    "/maintenance/live-workload-target-profiles",
    response_model=LiveWorkloadTargetProfileResponse,
    dependencies=[Depends(require_api_key)],
)
async def upsert_live_workload_target_profile(
    request: UpsertLiveWorkloadTargetProfileRequest,
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> LiveWorkloadTargetProfileResponse:
    _require_oauth_feature(actor, settings.oauth_targets_app_id)
    _require_organization_scope(actor, request.organization_name or settings.organization_name)
    _require_environment_scope(actor, request.environment_name or settings.environment_name)
    if request.team_name:
        _require_team_scope(actor, request.team_name)
    try:
        profile = _live_workload_target_profile_service().upsert_profile(
            name=request.name,
            approved_base_url=request.approved_target_base_url,
            drift_base_url=request.drift_target_base_url,
            organization_name=request.organization_name,
            team_name=request.team_name,
            project_name=request.project_name,
            environment_name=request.environment_name,
            approved_probe_url=request.approved_probe_url,
            drift_probe_url=request.drift_probe_url,
            approved_action_url=request.approved_action_url,
            drift_action_url=request.drift_action_url,
            approved_probe_method=request.approved_probe_method,
            drift_probe_method=request.drift_probe_method,
            approved_action_method=request.approved_action_method,
            drift_action_method=request.drift_action_method,
            approved_headers=request.approved_headers,
            drift_headers=request.drift_headers,
            approved_expected_statuses=request.approved_expected_statuses,
            drift_expected_statuses=request.drift_expected_statuses,
            request_timeout_seconds=request.request_timeout_seconds,
            enabled=request.enabled,
            description=request.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _append_privileged_api_audit(
        actor=actor,
        action="live-workload-target-profile-upsert",
        target=profile.name,
        outcome="ok",
        details=_privileged_audit_details(
            actor,
            target_profile=profile.name,
            approved_target_base_url=profile.approved_base_url,
            drift_target_base_url=profile.drift_base_url,
            organization_name=profile.organization_name,
            team_name=profile.team_name,
            project_name=profile.project_name,
            environment_name=profile.environment_name,
            approved_probe_url=profile.approved_probe_url,
            drift_probe_url=profile.drift_probe_url,
            approved_action_url=profile.approved_action_url,
            drift_action_url=profile.drift_action_url,
            approved_probe_method=profile.approved_probe_method,
            drift_probe_method=profile.drift_probe_method,
            approved_action_method=profile.approved_action_method,
            drift_action_method=profile.drift_action_method,
            approved_headers=profile.approved_headers,
            drift_headers=profile.drift_headers,
            approved_expected_statuses=profile.approved_expected_statuses,
            drift_expected_statuses=profile.drift_expected_statuses,
            request_timeout_seconds=profile.request_timeout_seconds,
            enabled=profile.enabled,
            source=profile.source,
        ),
    )
    return LiveWorkloadTargetProfileResponse(**profile.to_dict())


@app.delete(
    "/maintenance/live-workload-target-profiles/{profile_name}",
    response_model=dict[str, object],
    dependencies=[Depends(require_api_key)],
)
async def delete_live_workload_target_profile(
    profile_name: str,
    request: DeleteLiveWorkloadTargetProfileRequest,
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> dict[str, object]:
    _require_oauth_feature(actor, settings.oauth_targets_app_id)
    profile = _require_live_workload_target_profile(profile_name)
    _require_live_workload_target_profile_scope(actor, profile)
    try:
        existed = _live_workload_target_profile_service().delete_profile(profile_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _append_privileged_api_audit(
        actor=actor,
        action="live-workload-target-profile-delete",
        target=profile_name.strip().lower(),
        outcome="ok" if existed else "not_found",
        details=_privileged_audit_details(
            actor,
            target_profile=profile_name.strip().lower(),
            existed=existed,
            reason=request.reason,
        ),
    )
    return {
        "deleted": existed,
        "profile_name": profile_name.strip().lower(),
    }


@app.post(
    "/maintenance/live-workload-target-profiles/{profile_name}/validate",
    response_model=ControlPlaneLiveWorkloadTargetValidationResponse,
    dependencies=[Depends(require_api_key)],
)
async def run_live_workload_target_profile_validation(
    profile_name: str,
    request: RunLiveWorkloadTargetProfileValidationRequest,
    actor: ControlPlaneActor = Depends(require_targets_actor),
) -> ControlPlaneLiveWorkloadTargetValidationResponse:
    profile = _require_live_workload_target_profile(profile_name)
    _require_live_workload_target_profile_scope(actor, profile)
    summary = _control_plane_live_workload_target_validation_service().execute(
        changed_by=actor.actor_id,
        reason=request.reason,
        timeout_seconds=request.timeout_seconds,
        actor_details=_maintenance_actor_details(actor),
        target_profile_name=profile.name,
    )
    _append_privileged_api_audit(
        actor=actor,
        action="live-workload-target-profile-validation",
        target=profile.name,
        outcome="passed" if summary.status == "passed" else "failed",
        details=_privileged_audit_details(
            actor,
            reason=request.reason,
            target_profile=profile.name,
            target_mode=summary.target_mode,
            blockers=summary.blockers,
        ),
    )
    return ControlPlaneLiveWorkloadTargetValidationResponse(**summary.to_dict())


@app.post(
    "/maintenance/live-workload-target-profiles/{profile_name}/drift-proof",
    response_model=LiveWorkloadDriftProofResponse,
    dependencies=[Depends(require_api_key)],
)
async def run_live_workload_target_profile_drift_proof(
    profile_name: str,
    request: RunLiveWorkloadTargetProfileDriftProofRequest,
    actor: ControlPlaneActor = Depends(require_targets_actor),
) -> LiveWorkloadDriftProofResponse:
    profile = _require_live_workload_target_profile(profile_name)
    _require_live_workload_target_profile_scope(actor, profile)
    summary = _live_workload_drift_proof_service().run(
        changed_by=actor.actor_id,
        reason=request.reason,
        persist=request.persist,
        snapshot_id=request.snapshot_id,
        audit_id=request.audit_id,
        actor_details=_maintenance_actor_details(actor),
        target_profile_name=profile.name,
    )
    _append_privileged_api_audit(
        actor=actor,
        action="live-workload-target-profile-drift-proof",
        target=profile.name,
        outcome="passed" if summary.passed else "failed",
        details=_privileged_audit_details(
            actor,
            reason=request.reason,
            target_profile=profile.name,
            snapshot_id=summary.snapshot_id,
            audit_id=summary.audit_id,
            alert_count=summary.alert_count,
        ),
    )
    return LiveWorkloadDriftProofResponse(**summary.to_dict())


@app.post(
    "/maintenance/live-workload-target-profiles/{profile_name}/operational-validation",
    response_model=ControlPlaneOperationalValidationResponse,
    dependencies=[Depends(require_api_key)],
)
async def run_live_workload_target_profile_operational_validation(
    profile_name: str,
    request: RunControlPlaneOperationalValidationRequest,
    actor: ControlPlaneActor = Depends(require_targets_actor),
) -> ControlPlaneOperationalValidationResponse:
    profile = _require_live_workload_target_profile(profile_name)
    _require_live_workload_target_profile_scope(actor, profile)
    summary = _control_plane_operational_validation_service().run(
        changed_by=actor.actor_id,
        expected_backend=request.expected_backend,
        reason=request.reason,
        process_backups=request.process_backups,
        cleanup=request.cleanup,
        run_queue_validation=request.run_queue_validation,
        run_live_workload_drift_proof=request.run_live_workload_drift_proof,
        queue_success_jobs=request.queue_success_jobs,
        queue_failure_jobs=request.queue_failure_jobs,
        queue_delay_seconds=request.queue_delay_seconds,
        run_inline_queue_worker=request.run_inline_queue_worker,
        run_workload_validation=request.run_workload_validation,
        workload_rounds=request.workload_rounds,
        workload_maintenance_pause_jobs=request.workload_maintenance_pause_jobs,
        inject_maintenance_mode_pause=request.inject_maintenance_mode_pause,
        run_worker_recovery_validation=request.run_worker_recovery_validation,
        actor_details=_maintenance_actor_details(actor),
        target_profile_name=profile.name,
    )
    _append_privileged_api_audit(
        actor=actor,
        action="live-workload-target-profile-operational-validation",
        target=profile.name,
        outcome=summary.status,
        details=_privileged_audit_details(
            actor,
            reason=request.reason,
            target_profile=profile.name,
            expected_backend=request.expected_backend,
        ),
    )
    return ControlPlaneOperationalValidationResponse(**summary.to_dict())


@app.post(
    "/maintenance/live-workload-target-profiles/{profile_name}/canary-verify",
    response_model=ControlPlaneCanaryVerifierResponse,
    dependencies=[Depends(require_api_key)],
)
async def run_live_workload_target_profile_canary_verifier(
    profile_name: str,
    request: RunLiveWorkloadTargetProfileCanaryVerifierRequest,
    actor: ControlPlaneActor = Depends(require_targets_actor),
) -> ControlPlaneCanaryVerifierResponse:
    profile = _require_live_workload_target_profile(profile_name)
    _require_live_workload_target_profile_scope(actor, profile)
    summary = _control_plane_canary_verifier_service().run(
        changed_by=actor.actor_id,
        target_profile_name=profile.name,
        expected_backend=request.expected_backend,
        reason=request.reason,
        process_backups=request.process_backups,
        cleanup=request.cleanup,
        run_queue_validation=request.run_queue_validation,
        run_workload_validation=request.run_workload_validation,
        run_worker_recovery_validation=request.run_worker_recovery_validation,
        queue_success_jobs=request.queue_success_jobs,
        queue_failure_jobs=request.queue_failure_jobs,
        queue_delay_seconds=request.queue_delay_seconds,
        run_inline_queue_worker=request.run_inline_queue_worker,
        workload_rounds=request.workload_rounds,
        workload_maintenance_pause_jobs=request.workload_maintenance_pause_jobs,
        inject_maintenance_mode_pause=request.inject_maintenance_mode_pause,
        actor_details=_maintenance_actor_details(actor),
    )
    _append_privileged_api_audit(
        actor=actor,
        action="live-workload-target-profile-canary-verify",
        target=profile.name,
        outcome="passed" if summary.verdict == "promote" else "failed",
        details=_privileged_audit_details(
            actor,
            reason=request.reason,
            target_profile=profile.name,
            expected_backend=request.expected_backend,
            verdict=summary.verdict,
            blockers=summary.blockers,
        ),
    )
    return ControlPlaneCanaryVerifierResponse(**summary.to_dict())


@app.get(
    "/maintenance/live-workload-proof-bundles",
    response_model=list[LiveWorkloadProofBundleRecordResponse],
    dependencies=[Depends(require_api_key), Depends(require_reports_actor)],
)
async def list_live_workload_proof_bundles() -> list[LiveWorkloadProofBundleRecordResponse]:
    return [
        LiveWorkloadProofBundleRecordResponse(**record.to_dict())
        for record in _live_workload_proof_bundle_service().list_bundles()
    ]


@app.post(
    "/maintenance/live-workload-proof-bundles/export",
    response_model=LiveWorkloadProofBundleResponse,
    dependencies=[Depends(require_api_key)],
)
async def export_live_workload_proof_bundle(
    request: ExportLiveWorkloadProofBundleRequest,
    actor: ControlPlaneActor = Depends(require_reports_actor),
) -> LiveWorkloadProofBundleResponse:
    _require_environment_scope(actor, settings.environment_name)
    summary = _live_workload_proof_bundle_service().export_bundle(
        changed_by=actor.actor_id,
        reason=request.reason,
        actor_details=_maintenance_actor_details(actor),
    )
    return LiveWorkloadProofBundleResponse(**summary.to_dict())


@app.post(
    "/maintenance/live-workload-proof-bundles/prune",
    response_model=LiveWorkloadProofBundlePruneResponse,
    dependencies=[Depends(require_api_key)],
)
async def prune_live_workload_proof_bundles(
    request: PruneLiveWorkloadProofBundlesRequest,
    actor: ControlPlaneActor = Depends(require_reports_actor),
) -> LiveWorkloadProofBundlePruneResponse:
    _require_environment_scope(actor, settings.environment_name)
    result = _live_workload_proof_bundle_service().prune_bundles(
        changed_by=actor.actor_id,
        reason=request.reason,
        actor_details=_maintenance_actor_details(actor),
        retention_days=request.retention_days,
    )
    _append_privileged_api_audit(
        actor=actor,
        action="live-workload-proof-bundles-prune",
        target="live-workload-proof-bundles",
        outcome="passed",
        details=_privileged_audit_details(
            actor,
            reason=request.reason,
            retention_days=result.retention_days,
            pruned_count=result.pruned_count,
        ),
    )
    return LiveWorkloadProofBundlePruneResponse(**result.to_dict())


@app.post(
    "/maintenance/live-workload-proof-bundles/inspect",
    response_model=LiveWorkloadProofBundleInspectionResponse,
    dependencies=[Depends(require_api_key), Depends(require_reports_actor)],
)
async def inspect_live_workload_proof_bundle(
    request: InspectLiveWorkloadProofBundleRequest,
) -> LiveWorkloadProofBundleInspectionResponse:
    return LiveWorkloadProofBundleInspectionResponse(
        **_live_workload_proof_bundle_service().inspect_bundle(path=request.path).to_dict()
    )


@app.post(
    "/maintenance/live-workload-proof-bundles/delete",
    response_model=LiveWorkloadProofBundleDeleteResponse,
    dependencies=[Depends(require_api_key)],
)
async def delete_live_workload_proof_bundle(
    request: DeleteLiveWorkloadProofBundleRequest,
    actor: ControlPlaneActor = Depends(require_reports_actor),
) -> LiveWorkloadProofBundleDeleteResponse:
    _require_environment_scope(actor, settings.environment_name)
    result = _live_workload_proof_bundle_service().delete_bundle(
        path=request.path,
        changed_by=actor.actor_id,
        reason=request.reason,
        actor_details=_maintenance_actor_details(actor),
    )
    _append_privileged_api_audit(
        actor=actor,
        action="live-workload-proof-bundle-delete",
        target=request.path,
        outcome="passed",
        details=_privileged_audit_details(
            actor,
            reason=request.reason,
            existed=result.existed,
        ),
    )
    return LiveWorkloadProofBundleDeleteResponse(**result.to_dict())


@app.get(
    "/maintenance/control-plane-live-workload-target-validation",
    response_model=ControlPlaneLiveWorkloadTargetValidationResponse,
    dependencies=[Depends(require_api_key), Depends(require_reports_actor)],
)
async def get_control_plane_live_workload_target_validation() -> ControlPlaneLiveWorkloadTargetValidationResponse:
    return ControlPlaneLiveWorkloadTargetValidationResponse(
        **_control_plane_live_workload_target_validation_service().build_summary().to_dict()
    )


@app.post(
    "/maintenance/control-plane-live-workload-target-validation",
    response_model=ControlPlaneLiveWorkloadTargetValidationResponse,
    dependencies=[Depends(require_api_key)],
)
async def run_control_plane_live_workload_target_validation(
    request: RunLiveWorkloadTargetValidationRequest,
    actor: ControlPlaneActor = Depends(require_targets_actor),
) -> ControlPlaneLiveWorkloadTargetValidationResponse:
    _require_environment_scope(actor, settings.environment_name)
    summary = _control_plane_live_workload_target_validation_service().execute(
        changed_by=actor.actor_id,
        reason=request.reason,
        timeout_seconds=request.timeout_seconds,
        actor_details=_maintenance_actor_details(actor),
    )
    _record_privileged_api_audit(
        actor=actor,
        action="live-workload-target-validation",
        target="sample-service-targets",
        outcome="passed" if summary.status == "passed" else "failed",
        details=_privileged_audit_details(
            actor,
            reason=request.reason,
            target_profile=summary.target_profile,
            target_mode=summary.target_mode,
            blockers=summary.blockers,
        ),
    )
    return ControlPlaneLiveWorkloadTargetValidationResponse(**summary.to_dict())


@app.get(
    "/maintenance/control-plane-live-workload-proof-validation",
    response_model=ControlPlaneLiveWorkloadProofValidationResponse,
    dependencies=[Depends(require_api_key), Depends(require_reports_actor)],
)
async def get_control_plane_live_workload_proof_validation() -> ControlPlaneLiveWorkloadProofValidationResponse:
    return ControlPlaneLiveWorkloadProofValidationResponse(
        **_control_plane_live_workload_proof_validation_service().build_summary().to_dict()
    )


@app.get(
    "/maintenance/control-plane-trust-score",
    response_model=ControlPlaneTrustScoreResponse,
    dependencies=[Depends(require_api_key), Depends(require_reports_actor)],
)
async def get_control_plane_trust_score() -> ControlPlaneTrustScoreResponse:
    return ControlPlaneTrustScoreResponse(**_control_plane_trust_score_service().build_summary().to_dict())


@app.get(
    "/maintenance/control-plane-incident-narrative",
    response_model=ControlPlaneIncidentNarrativeResponse,
    dependencies=[Depends(require_api_key), Depends(require_reports_actor)],
)
async def get_control_plane_incident_narrative() -> ControlPlaneIncidentNarrativeResponse:
    return ControlPlaneIncidentNarrativeResponse(**_control_plane_incident_narrative_service().build_summary().to_dict())


@app.get(
    "/maintenance/control-plane-backup-validation",
    response_model=ControlPlaneBackupValidationResponse,
    dependencies=[Depends(require_api_key), Depends(require_reports_actor)],
)
async def get_control_plane_backup_validation() -> ControlPlaneBackupValidationResponse:
    return ControlPlaneBackupValidationResponse(**_control_plane_backup_validation_service().build_summary().to_dict())


@app.get(
    "/maintenance/control-plane-operational-validation-status",
    response_model=ControlPlaneOperationalValidationEvidenceResponse,
    dependencies=[Depends(require_api_key), Depends(require_reports_actor)],
)
async def get_control_plane_operational_validation_status() -> ControlPlaneOperationalValidationEvidenceResponse:
    return ControlPlaneOperationalValidationEvidenceResponse(
        **_control_plane_operational_validation_evidence_service().build_summary().to_dict()
    )


@app.get(
    "/maintenance/control-plane-soak-validation-status",
    response_model=ControlPlaneSoakValidationEvidenceResponse,
    dependencies=[Depends(require_api_key), Depends(require_reports_actor)],
)
async def get_control_plane_soak_validation_status() -> ControlPlaneSoakValidationEvidenceResponse:
    return ControlPlaneSoakValidationEvidenceResponse(
        **_control_plane_soak_validation_evidence_service().build_summary().to_dict()
    )


@app.post(
    "/maintenance/control-plane-observability-export",
    response_model=ControlPlaneObservabilityExportResponse,
    dependencies=[Depends(require_api_key)],
)
async def export_control_plane_observability(
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneObservabilityExportResponse:
    summary = control_plane_observability_export_service.export_snapshot(
        changed_by=actor.actor_id,
        reason="manual observability export",
        actor_details=_maintenance_actor_details(actor),
    )
    return ControlPlaneObservabilityExportResponse(**summary.to_dict())


@app.get(
    "/maintenance/control-plane-observability-export-validation",
    response_model=ControlPlaneObservabilityExportValidationResponse,
    dependencies=[Depends(require_api_key), Depends(require_reports_actor)],
)
async def get_control_plane_observability_export_validation() -> ControlPlaneObservabilityExportValidationResponse:
    return ControlPlaneObservabilityExportValidationResponse(
        **control_plane_observability_export_service.latest_export_validation().to_dict()
    )


@app.get(
    "/maintenance/control-plane-observability-exports",
    response_model=list[ControlPlaneObservabilityBundlePayload],
    dependencies=[Depends(require_api_key)],
)
async def list_control_plane_observability_exports(
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> list[ControlPlaneObservabilityBundlePayload]:
    _require_oauth_feature(actor, settings.oauth_reports_app_id)
    _append_privileged_api_audit(
        actor=actor,
        action="observability-export-list",
        target="control-plane-observability-exports",
        outcome="ok",
    )
    return [
        ControlPlaneObservabilityBundlePayload(**record.to_dict())
        for record in control_plane_observability_export_service.list_exports()
    ]


@app.get(
    "/maintenance/control-plane-backup-export-validation",
    response_model=ControlPlaneBackupExportValidationResponse,
    dependencies=[Depends(require_api_key), Depends(require_reports_actor)],
)
async def get_control_plane_backup_export_validation() -> ControlPlaneBackupExportValidationResponse:
    return ControlPlaneBackupExportValidationResponse(
        **_control_plane_backup_operations_service().latest_backup_export_validation().to_dict()
    )


@app.get(
    "/maintenance/control-plane-backups",
    response_model=list[ControlPlaneBackupBundlePayload],
    dependencies=[Depends(require_api_key)],
)
async def list_control_plane_backups(
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> list[ControlPlaneBackupBundlePayload]:
    _require_oauth_feature(actor, settings.oauth_reports_app_id)
    _append_privileged_api_audit(
        actor=actor,
        action="backup-list",
        target="control-plane-backups",
        outcome="ok",
    )
    return [
        ControlPlaneBackupBundlePayload(**record.to_dict())
        for record in _control_plane_backup_operations_service().list_backup_bundles()
    ]


@app.post(
    "/maintenance/control-plane-backups/process",
    response_model=ProcessControlPlaneBackupsResponse,
    dependencies=[Depends(require_api_key)],
)
async def process_control_plane_backups(
    request: ProcessControlPlaneBackupsRequest,
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> ProcessControlPlaneBackupsResponse:
    result = _control_plane_backup_operations_service().process_scheduled_backups(
        changed_by=actor.actor_id,
        reason=request.reason,
        force=request.force,
        actor_details=_maintenance_actor_details(actor),
    )
    _append_privileged_api_audit(
        actor=actor,
        action="backup-process",
        target="control-plane-backups",
        outcome="ok",
        details=_privileged_audit_details(actor, reason=request.reason, force=request.force),
    )
    return ProcessControlPlaneBackupsResponse(**result.to_dict())


@app.get(
    "/maintenance/control-plane-deployment-readiness",
    response_model=ControlPlaneDeploymentReadinessResponse,
    dependencies=[Depends(require_api_key), Depends(require_reports_actor)],
)
async def get_control_plane_deployment_readiness() -> ControlPlaneDeploymentReadinessResponse:
    return ControlPlaneDeploymentReadinessResponse(**_control_plane_deployment_readiness_service().evaluate().to_dict())


@app.get(
    "/maintenance/control-plane-runtime-validation-reviews",
    response_model=list[ControlPlaneRuntimeValidationReviewPayload],
    dependencies=[Depends(require_api_key), Depends(require_reviews_actor)],
)
async def list_control_plane_runtime_validation_reviews(
    status: str | None = Query(default=None),
    owner_team: str | None = Query(default=None),
    assignment_state: str | None = Query(default=None),
    actor: ControlPlaneActor = Depends(require_reviews_actor),
) -> list[ControlPlaneRuntimeValidationReviewPayload]:
    return [
        ControlPlaneRuntimeValidationReviewPayload(**record.to_dict())
        for record in job_service.list_runtime_validation_reviews_scoped(
            actor=_authorized_actor(actor),
            status=status,
            owner_team=owner_team,
            assignment_state=assignment_state,
        )
    ]


@app.get(
    "/maintenance/control-plane-runtime-validation-governance-requests",
    response_model=list[ControlPlaneRuntimeValidationGovernancePayload],
    dependencies=[Depends(require_api_key), Depends(require_reviews_actor)],
)
async def list_control_plane_runtime_validation_governance_requests(
    status: str | None = Query(default=None),
    owner_team: str | None = Query(default=None),
    actor: ControlPlaneActor = Depends(require_reviews_actor),
) -> list[ControlPlaneRuntimeValidationGovernancePayload]:
    return [
        ControlPlaneRuntimeValidationGovernancePayload(**record.to_dict())
        for record in job_service.list_runtime_validation_governance_requests_scoped(
            actor=_authorized_actor(actor),
            status=status,
            owner_team=owner_team,
        )
    ]


@app.get(
    "/maintenance/control-plane-runtime-validation-change-control-requests",
    response_model=list[ControlPlaneRuntimeValidationChangeControlPayload],
    dependencies=[Depends(require_api_key), Depends(require_reviews_actor)],
)
async def list_control_plane_runtime_validation_change_control_requests(
    status: str | None = Query(default=None),
    owner_team: str | None = Query(default=None),
    actor: ControlPlaneActor = Depends(require_reviews_actor),
) -> list[ControlPlaneRuntimeValidationChangeControlPayload]:
    return [
        ControlPlaneRuntimeValidationChangeControlPayload(**record.to_dict())
        for record in job_service.list_runtime_validation_change_control_requests_scoped(
            actor=_authorized_actor(actor),
            status=status,
            owner_team=owner_team,
        )
    ]


@app.get(
    "/maintenance/control-plane-deployment-readiness/owner-team-queue",
    response_model=ControlPlaneRuntimeValidationChangeControlQueuePayload,
    dependencies=[Depends(require_api_key), Depends(require_reports_actor)],
)
async def get_control_plane_deployment_readiness_owner_team_queue(
    status: str | None = Query(default=None),
    owner_team: str | None = Query(default=None),
    assignment_state: str | None = Query(default=None),
    actor: ControlPlaneActor = Depends(require_reports_actor),
) -> ControlPlaneRuntimeValidationChangeControlQueuePayload:
    summary = job_service.runtime_validation_change_control_queue_summary_scoped(
        actor=_authorized_actor(actor),
        status=status,
        owner_team=owner_team,
        assignment_state=assignment_state,
    )
    if summary is None:
        raise HTTPException(status_code=500, detail="Runtime-validation review service is not configured.")
    return ControlPlaneRuntimeValidationChangeControlQueuePayload(**summary.to_dict())


@app.get(
    "/maintenance/control-plane-deployment-readiness/owner-team-queue.csv",
    response_class=PlainTextResponse,
    dependencies=[Depends(require_api_key), Depends(require_reports_actor)],
)
async def export_control_plane_deployment_readiness_owner_team_queue_csv(
    status: str | None = Query(default=None),
    owner_team: str | None = Query(default=None),
    assignment_state: str | None = Query(default=None),
    actor: ControlPlaneActor = Depends(require_reports_actor),
) -> PlainTextResponse:
    scoped_owner_team = job_service.authorization_service.scoped_owner_team(_authorized_actor(actor), owner_team) if job_service.authorization_service else owner_team
    owner_label = (scoped_owner_team or "all").replace("/", "-")
    return PlainTextResponse(
        _render_deployment_readiness_owner_team_queue_csv(
            status=status,
            owner_team=scoped_owner_team,
            assignment_state=assignment_state,
        ),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="deployment-readiness-owner-team-queue-{owner_label}.csv"'
            )
        },
    )


@app.get(
    "/maintenance/control-plane-runtime-validation-review-queue",
    response_model=ControlPlaneRuntimeValidationReviewQueuePayload,
    dependencies=[Depends(require_api_key), Depends(require_reviews_actor)],
)
async def get_control_plane_runtime_validation_review_queue(
    status: str | None = Query(default=None),
    owner_team: str | None = Query(default=None),
    assignment_state: str | None = Query(default=None),
    actor: ControlPlaneActor = Depends(require_reviews_actor),
) -> ControlPlaneRuntimeValidationReviewQueuePayload:
    summary = job_service.runtime_validation_review_queue_summary_scoped(
        actor=_authorized_actor(actor),
        status=status,
        owner_team=owner_team,
        assignment_state=assignment_state,
    )
    if summary is None:
        raise HTTPException(status_code=500, detail="Runtime-validation review service is not configured.")
    return ControlPlaneRuntimeValidationReviewQueuePayload(**summary.to_dict())


@app.get(
    "/maintenance/control-plane-runtime-validation-review-queue.csv",
    response_class=PlainTextResponse,
    dependencies=[Depends(require_api_key), Depends(require_reviews_actor)],
)
async def export_control_plane_runtime_validation_review_queue_csv(
    status: str | None = Query(default=None),
    owner_team: str | None = Query(default=None),
    assignment_state: str | None = Query(default=None),
    actor: ControlPlaneActor = Depends(require_reviews_actor),
) -> PlainTextResponse:
    scoped_owner_team = job_service.authorization_service.scoped_owner_team(_authorized_actor(actor), owner_team) if job_service.authorization_service else owner_team
    owner_label = (scoped_owner_team or "all").replace("/", "-")
    return PlainTextResponse(
        _render_runtime_validation_review_queue_csv(
            status=status,
            owner_team=scoped_owner_team,
            assignment_state=assignment_state,
        ),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="runtime-validation-review-queue-{owner_label}.csv"'
            )
        },
    )


@app.post(
    "/maintenance/control-plane-runtime-validation-reviews/process",
    response_model=list[ControlPlaneRuntimeValidationReviewPayload],
    dependencies=[Depends(require_api_key)],
)
async def process_control_plane_runtime_validation_reviews(
    request: ProcessRuntimeValidationReviewsRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> list[ControlPlaneRuntimeValidationReviewPayload]:
    _require_environment_scope(actor, settings.environment_name)
    records = [
        ControlPlaneRuntimeValidationReviewPayload(**record.to_dict())
        for record in job_service.process_runtime_validation_reviews(
            changed_by=actor.actor_id,
            reason=request.reason,
            force=request.force,
            actor_details=_maintenance_actor_details(actor),
        )
    ]
    _append_privileged_api_audit(
        actor=actor,
        action="process-runtime-validation-reviews",
        target="runtime-validation-reviews",
        outcome=str(len(records)),
    )
    return records


@app.post(
    "/maintenance/control-plane-runtime-validation-governance-requests/process",
    response_model=list[ControlPlaneRuntimeValidationGovernancePayload],
    dependencies=[Depends(require_api_key)],
)
async def process_control_plane_runtime_validation_governance_requests(
    request: ProcessRuntimeValidationGovernanceRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> list[ControlPlaneRuntimeValidationGovernancePayload]:
    _require_environment_scope(actor, settings.environment_name)
    records = [
        ControlPlaneRuntimeValidationGovernancePayload(**record.to_dict())
        for record in job_service.process_runtime_validation_governance(
            changed_by=actor.actor_id,
            reason=request.reason,
            force=request.force,
            actor_details=_maintenance_actor_details(actor),
        )
    ]
    _append_privileged_api_audit(
        actor=actor,
        action="process-runtime-validation-governance",
        target="runtime-validation-governance",
        outcome=str(len(records)),
    )
    return records


@app.post(
    "/maintenance/control-plane-runtime-validation-change-control-requests/process",
    response_model=list[ControlPlaneRuntimeValidationChangeControlPayload],
    dependencies=[Depends(require_api_key)],
)
async def process_control_plane_runtime_validation_change_control_requests(
    request: ProcessRuntimeValidationChangeControlRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> list[ControlPlaneRuntimeValidationChangeControlPayload]:
    _require_environment_scope(actor, settings.environment_name)
    records = [
        ControlPlaneRuntimeValidationChangeControlPayload(**record.to_dict())
        for record in job_service.process_runtime_validation_change_control(
            changed_by=actor.actor_id,
            reason=request.reason,
            force=request.force,
            actor_details=_maintenance_actor_details(actor),
        )
    ]
    _append_privileged_api_audit(
        actor=actor,
        action="process-runtime-validation-change-control",
        target="runtime-validation-change-control",
        outcome=str(len(records)),
    )
    return records


@app.post(
    "/maintenance/control-plane-runtime-validation-change-control-requests/{request_id}/assign",
    response_model=ControlPlaneRuntimeValidationChangeControlPayload,
    dependencies=[Depends(require_api_key)],
)
async def assign_control_plane_runtime_validation_change_control_request(
    request_id: str,
    request: AssignRuntimeValidationChangeControlRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneRuntimeValidationChangeControlPayload:
    try:
        record = job_service.assign_runtime_validation_change_control_request_scoped(
            actor=_authorized_actor(actor),
            request_id=request_id,
            assigned_to=request.assigned_to,
            assigned_to_team=request.assigned_to_team,
            assigned_by=actor.actor_id,
            assignment_note=request.assignment_note,
            actor_details=_maintenance_actor_details(actor),
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _append_privileged_api_audit(
        actor=actor,
        action="assign-runtime-validation-change-control",
        target=request_id,
        outcome=record.status,
    )
    return ControlPlaneRuntimeValidationChangeControlPayload(**record.to_dict())


@app.post(
    "/maintenance/control-plane-runtime-validation-change-control-requests/{request_id}/review",
    response_model=ControlPlaneRuntimeValidationChangeControlPayload,
    dependencies=[Depends(require_api_key)],
)
async def review_control_plane_runtime_validation_change_control_request(
    request_id: str,
    request: ReviewRuntimeValidationChangeControlRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneRuntimeValidationChangeControlPayload:
    try:
        record = job_service.decide_runtime_validation_change_control_request_scoped(
            actor=_authorized_actor(actor),
            request_id=request_id,
            decision=request.decision,
            decided_by=actor.actor_id,
            decision_note=request.decision_note,
            actor_details=_maintenance_actor_details(actor),
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _append_privileged_api_audit(
        actor=actor,
        action="review-runtime-validation-change-control",
        target=request_id,
        outcome=record.status,
    )
    return ControlPlaneRuntimeValidationChangeControlPayload(**record.to_dict())


@app.post(
    "/maintenance/control-plane-runtime-validation-change-control-requests/bulk-assign",
    response_model=ControlPlaneRuntimeValidationChangeControlBulkActionPayload,
    dependencies=[Depends(require_api_key)],
)
async def bulk_assign_control_plane_runtime_validation_change_control_requests(
    request: BulkAssignRuntimeValidationChangeControlRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneRuntimeValidationChangeControlBulkActionPayload:
    try:
        result = job_service.bulk_assign_runtime_validation_change_control_requests_scoped(
            actor=_authorized_actor(actor),
            assigned_to=request.assigned_to,
            assigned_to_team=request.assigned_to_team,
            assigned_by=actor.actor_id,
            assignment_note=request.assignment_note,
            status=request.status,
            owner_team=request.owner_team,
            assignment_state=request.assignment_state,
            actor_details=_maintenance_actor_details(actor),
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ControlPlaneRuntimeValidationChangeControlBulkActionPayload(**result.to_dict())


@app.post(
    "/maintenance/control-plane-runtime-validation-change-control-requests/bulk-review",
    response_model=ControlPlaneRuntimeValidationChangeControlBulkActionPayload,
    dependencies=[Depends(require_api_key)],
)
async def bulk_review_control_plane_runtime_validation_change_control_requests(
    request: BulkReviewRuntimeValidationChangeControlRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneRuntimeValidationChangeControlBulkActionPayload:
    try:
        result = job_service.bulk_decide_runtime_validation_change_control_requests_scoped(
            actor=_authorized_actor(actor),
            decision=request.decision,
            decided_by=actor.actor_id,
            decision_note=request.decision_note,
            status=request.status,
            owner_team=request.owner_team,
            assignment_state=request.assignment_state,
            actor_details=_maintenance_actor_details(actor),
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ControlPlaneRuntimeValidationChangeControlBulkActionPayload(**result.to_dict())


@app.post(
    "/maintenance/control-plane-runtime-validation-reviews/{review_id}/assign",
    response_model=ControlPlaneRuntimeValidationReviewPayload,
    dependencies=[Depends(require_api_key)],
)
async def assign_control_plane_runtime_validation_review(
    review_id: str,
    request: AssignRuntimeValidationReviewRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneRuntimeValidationReviewPayload:
    try:
        record = job_service.assign_runtime_validation_review_scoped(
            actor=_authorized_actor(actor),
            review_id=review_id,
            assigned_to=request.assigned_to,
            assigned_to_team=request.assigned_to_team,
            assigned_by=actor.actor_id,
            assignment_note=request.assignment_note,
            actor_details=_maintenance_actor_details(actor),
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _append_privileged_api_audit(
        actor=actor,
        action="assign-runtime-validation-review",
        target=review_id,
        outcome=record.status,
    )
    return ControlPlaneRuntimeValidationReviewPayload(**record.to_dict())


@app.post(
    "/maintenance/control-plane-runtime-validation-reviews/bulk-assign",
    response_model=ControlPlaneRuntimeValidationReviewBulkActionPayload,
    dependencies=[Depends(require_api_key)],
)
async def bulk_assign_control_plane_runtime_validation_reviews(
    request: BulkAssignRuntimeValidationReviewsRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneRuntimeValidationReviewBulkActionPayload:
    try:
        result = job_service.bulk_assign_runtime_validation_reviews_scoped(
            actor=_authorized_actor(actor),
            assigned_to=request.assigned_to,
            assigned_to_team=request.assigned_to_team,
            assigned_by=actor.actor_id,
            assignment_note=request.assignment_note,
            status=request.status,
            owner_team=request.owner_team,
            assignment_state=request.assignment_state,
            actor_details=_maintenance_actor_details(actor),
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ControlPlaneRuntimeValidationReviewBulkActionPayload(**result.to_dict())


@app.post(
    "/maintenance/control-plane-runtime-validation-reviews/{review_id}/resolve",
    response_model=ControlPlaneRuntimeValidationReviewPayload,
    dependencies=[Depends(require_api_key)],
)
async def resolve_control_plane_runtime_validation_review(
    review_id: str,
    request: ResolveRuntimeValidationReviewRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneRuntimeValidationReviewPayload:
    try:
        record = job_service.resolve_runtime_validation_review_scoped(
            actor=_authorized_actor(actor),
            review_id=review_id,
            resolved_by=actor.actor_id,
            resolution_note=request.resolution_note,
            resolution_reason=request.resolution_reason,
            actor_details=_maintenance_actor_details(actor),
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _append_privileged_api_audit(
        actor=actor,
        action="resolve-runtime-validation-review",
        target=review_id,
        outcome=record.status,
    )
    return ControlPlaneRuntimeValidationReviewPayload(**record.to_dict())


@app.post(
    "/maintenance/control-plane-runtime-validation-reviews/bulk-resolve",
    response_model=ControlPlaneRuntimeValidationReviewBulkActionPayload,
    dependencies=[Depends(require_api_key)],
)
async def bulk_resolve_control_plane_runtime_validation_reviews(
    request: BulkResolveRuntimeValidationReviewsRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneRuntimeValidationReviewBulkActionPayload:
    try:
        result = job_service.bulk_resolve_runtime_validation_reviews_scoped(
            actor=_authorized_actor(actor),
            resolved_by=actor.actor_id,
            resolution_note=request.resolution_note,
            resolution_reason=request.resolution_reason,
            status=request.status,
            owner_team=request.owner_team,
            assignment_state=request.assignment_state,
            actor_details=_maintenance_actor_details(actor),
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ControlPlaneRuntimeValidationReviewBulkActionPayload(**result.to_dict())


@app.get(
    "/maintenance/control-plane-cutover-preflight",
    response_model=ControlPlaneCutoverPreflightResponse,
    dependencies=[Depends(require_api_key)],
)
async def get_control_plane_cutover_preflight(
    target_database_url: str = Query(..., min_length=1),
) -> ControlPlaneCutoverPreflightResponse:
    try:
        summary = control_plane_cutover_service.build_preflight(target_database_url=target_database_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ControlPlaneCutoverPreflightResponse(**summary.to_dict())


@app.get(
    "/maintenance/control-plane-runtime-backend",
    response_model=ControlPlaneRuntimeBackendResponse,
    dependencies=[Depends(require_api_key)],
)
async def get_control_plane_runtime_backend() -> ControlPlaneRuntimeBackendResponse:
    database_status = job_repository.database_status()
    return ControlPlaneRuntimeBackendResponse(
        backend=str(database_status["backend"]),
        url=str(database_status["url"]),
        redacted_url=str(database_status["redacted_url"]),
        runtime_supported=bool(database_status["runtime_supported"]),
        runtime_driver=str(database_status["runtime_driver"]),
        runtime_dependency_installed=bool(database_status["runtime_dependency_installed"]),
        runtime_available=bool(database_status["runtime_available"]),
        runtime_blockers=[str(item) for item in database_status["runtime_blockers"]],
    )


@app.post(
    "/maintenance/control-plane-runtime-backend/inspect",
    response_model=ControlPlaneRuntimeBackendResponse,
    dependencies=[Depends(require_api_key)],
)
async def inspect_control_plane_runtime_backend(
    request: InspectControlPlaneRuntimeBackendRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneRuntimeBackendResponse:
    try:
        summary = inspect_database_runtime_support(
            root_dir=settings.root_dir,
            default_path=settings.database_path,
            raw_url=request.database_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ControlPlaneRuntimeBackendResponse(**summary.to_dict())


@app.post(
    "/maintenance/postgres-runtime-shadow-sync",
    response_model=PostgresRuntimeShadowSyncResponse,
    dependencies=[Depends(require_api_key)],
)
async def sync_postgres_runtime_shadow(
    request: SyncPostgresRuntimeShadowRequest,
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> PostgresRuntimeShadowSyncResponse:
    try:
        summary = _postgres_runtime_shadow_service().sync_control_plane_slice(
            target_database_url=request.target_database_url,
            changed_by=actor.actor_id,
            reason=request.reason,
            actor_details=_maintenance_actor_details(actor),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PostgresRuntimeShadowSyncResponse(**summary.to_dict())


@app.get(
    "/maintenance/events",
    response_model=list[ControlPlaneMaintenanceEventPayload],
    dependencies=[Depends(require_api_key)],
)
async def list_control_plane_maintenance_events(
    limit: int = Query(default=50, ge=1, le=500),
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> list[ControlPlaneMaintenanceEventPayload]:
    return [
        ControlPlaneMaintenanceEventPayload(**record.to_dict())
        for record in job_service.list_control_plane_maintenance_events_scoped(
            actor=_authorized_actor(actor),
            limit=limit,
        )
    ]


@app.get(
    "/maintenance/privileged-api-audit",
    response_model=list[PrivilegedApiAuditEntryPayload],
    dependencies=[Depends(require_api_key)],
)
async def list_privileged_api_audit(
    limit: int = Query(default=100, ge=1, le=1000),
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> list[PrivilegedApiAuditEntryPayload]:
    return [PrivilegedApiAuditEntryPayload(**record) for record in _read_privileged_api_audit(limit)]


@app.get(
    "/maintenance/privileged-api-audit/summary",
    response_model=PrivilegedApiAuditAnalyticsPayload,
    dependencies=[Depends(require_api_key)],
)
async def get_privileged_api_audit_summary(
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> PrivilegedApiAuditAnalyticsPayload:
    summary = PrivilegedApiAuditService(settings.privileged_api_audit_log_path).build_summary(window_hours=24.0)
    return PrivilegedApiAuditAnalyticsPayload(**summary.to_dict())


@app.post(
    "/maintenance/privileged-api-audit/prune",
    response_model=PrunePrivilegedApiAuditResponse,
    dependencies=[Depends(require_api_key)],
)
async def prune_privileged_api_audit(
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> PrunePrivilegedApiAuditResponse:
    result = PrivilegedApiAuditService(settings.privileged_api_audit_log_path).prune(
        retention_days=settings.privileged_api_audit_retention_days
    )
    _append_privileged_api_audit(
        actor=actor,
        action="prune-privileged-api-audit",
        target="privileged-api-audit",
        outcome="ok",
        details=_privileged_audit_details(actor, **result.to_dict()),
    )
    return PrunePrivilegedApiAuditResponse(**result.to_dict())


@app.post(
    "/maintenance/mode/enable",
    response_model=ControlPlaneMaintenanceModeResponse,
    dependencies=[Depends(require_api_key)],
)
async def enable_control_plane_maintenance_mode(
    request: SetControlPlaneMaintenanceModeRequest,
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> ControlPlaneMaintenanceModeResponse:
    result = job_service.enable_maintenance_mode(
        changed_by=actor.actor_id,
        reason=request.reason,
        actor_details=_maintenance_actor_details(actor),
    )
    _append_privileged_api_audit(
        actor=actor,
        action="enable-maintenance-mode",
        target="control-plane",
        outcome="ok",
        details=_privileged_audit_details(actor, reason=request.reason),
    )
    return ControlPlaneMaintenanceModeResponse(**result)


@app.post(
    "/maintenance/mode/disable",
    response_model=ControlPlaneMaintenanceModeResponse,
    dependencies=[Depends(require_api_key)],
)
async def disable_control_plane_maintenance_mode(
    request: SetControlPlaneMaintenanceModeRequest,
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> ControlPlaneMaintenanceModeResponse:
    result = job_service.disable_maintenance_mode(
        changed_by=actor.actor_id,
        reason=request.reason,
        actor_details=_maintenance_actor_details(actor),
    )
    _append_privileged_api_audit(
        actor=actor,
        action="disable-maintenance-mode",
        target="control-plane",
        outcome="ok",
        details=_privileged_audit_details(actor, reason=request.reason),
    )
    return ControlPlaneMaintenanceModeResponse(**result)


@app.post(
    "/maintenance/control-plane-runbook",
    response_model=RunControlPlaneMaintenanceWorkflowResponse,
    dependencies=[Depends(require_api_key)],
)
async def run_control_plane_maintenance_workflow(
    request: RunControlPlaneMaintenanceWorkflowRequest,
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> RunControlPlaneMaintenanceWorkflowResponse:
    try:
        summary = control_plane_maintenance_service.execute_workflow(
            output_path=request.output_path,
            changed_by=actor.actor_id,
            reason=request.reason,
            allow_running_jobs=request.allow_running_jobs,
            disable_maintenance_on_success=request.disable_maintenance_on_success,
            actor_details=_maintenance_actor_details(actor),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _append_privileged_api_audit(
        actor=actor,
        action="control-plane-runbook",
        target=request.output_path,
        outcome="ok",
    )
    return RunControlPlaneMaintenanceWorkflowResponse(**summary.to_dict())


@app.post(
    "/maintenance/control-plane-cutover-bundle",
    response_model=PrepareControlPlaneCutoverBundleResponse,
    dependencies=[Depends(require_api_key)],
)
async def prepare_control_plane_cutover_bundle(
    request: PrepareControlPlaneCutoverBundleRequest,
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> PrepareControlPlaneCutoverBundleResponse:
    try:
        summary = control_plane_cutover_service.prepare_cutover_bundle(
            output_path=request.output_path,
            target_database_url=request.target_database_url,
            changed_by=actor.actor_id,
            reason=request.reason,
            allow_running_jobs=request.allow_running_jobs,
            disable_maintenance_on_success=request.disable_maintenance_on_success,
            actor_details=_maintenance_actor_details(actor),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _append_privileged_api_audit(
        actor=actor,
        action="prepare-cutover-bundle",
        target=request.target_database_url,
        outcome="ok",
    )
    return PrepareControlPlaneCutoverBundleResponse(**summary.to_dict())


@app.post(
    "/maintenance/postgres-bootstrap-package/inspect",
    response_model=PostgresBootstrapPackageInspectionResponse,
    dependencies=[Depends(require_api_key)],
)
async def inspect_postgres_bootstrap_package(
    request: InspectPostgresBootstrapPackageRequest,
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> PostgresBootstrapPackageInspectionResponse:
    try:
        summary = postgres_bootstrap_service.inspect_package(package_dir=request.package_dir)
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PostgresBootstrapPackageInspectionResponse(**summary.to_dict())


@app.post(
    "/maintenance/postgres-bootstrap-package/plan",
    response_model=PostgresBootstrapExecutionPlanResponse,
    dependencies=[Depends(require_api_key)],
)
async def build_postgres_bootstrap_execution_plan(
    request: BuildPostgresBootstrapExecutionPlanRequest,
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> PostgresBootstrapExecutionPlanResponse:
    try:
        summary = postgres_bootstrap_service.build_execution_plan(
            package_dir=request.package_dir,
            target_database_url=request.target_database_url,
            artifact_target_root=request.artifact_target_root,
            psql_executable=request.psql_executable,
        )
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PostgresBootstrapExecutionPlanResponse(**summary.to_dict())


@app.post(
    "/maintenance/postgres-bootstrap-package/execute",
    response_model=ExecutePostgresBootstrapPackageResponse,
    dependencies=[Depends(require_api_key)],
)
async def execute_postgres_bootstrap_package(
    request: ExecutePostgresBootstrapPackageRequest,
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> ExecutePostgresBootstrapPackageResponse:
    try:
        summary = postgres_bootstrap_service.execute_package(
            package_dir=request.package_dir,
            target_database_url=request.target_database_url,
            artifact_target_root=request.artifact_target_root,
            psql_executable=request.psql_executable,
            dry_run=request.dry_run,
        )
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ExecutePostgresBootstrapPackageResponse(**summary.to_dict())


@app.post(
    "/maintenance/postgres-target/inspect",
    response_model=PostgresTargetInspectionResponse,
    dependencies=[Depends(require_api_key)],
)
async def inspect_postgres_target(
    request: InspectPostgresTargetRequest,
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> PostgresTargetInspectionResponse:
    try:
        summary = postgres_target_service.inspect_target(
            target_database_url=request.target_database_url,
            psql_executable=request.psql_executable,
        )
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PostgresTargetInspectionResponse(**summary.to_dict())


@app.post(
    "/maintenance/postgres-bootstrap-package/verify-target",
    response_model=VerifyPostgresBootstrapPackageResponse,
    dependencies=[Depends(require_api_key)],
)
async def verify_postgres_bootstrap_package_target(
    request: VerifyPostgresBootstrapPackageRequest,
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> VerifyPostgresBootstrapPackageResponse:
    try:
        summary = postgres_target_service.verify_bootstrap_package_against_target(
            package_dir=request.package_dir,
            target_database_url=request.target_database_url,
            psql_executable=request.psql_executable,
        )
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return VerifyPostgresBootstrapPackageResponse(**summary.to_dict())


@app.post(
    "/maintenance/postgres-cutover-rehearsal",
    response_model=PostgresCutoverRehearsalResponse,
    dependencies=[Depends(require_api_key)],
)
async def run_postgres_cutover_rehearsal(
    request: RunPostgresCutoverRehearsalRequest,
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> PostgresCutoverRehearsalResponse:
    try:
        summary = _postgres_cutover_rehearsal_service().execute_rehearsal(
            package_dir=request.package_dir,
            target_database_url=request.target_database_url,
            changed_by=actor.actor_id,
            reason=request.reason,
            psql_executable=request.psql_executable,
            artifact_target_root=request.artifact_target_root,
            apply_to_target=request.apply_to_target,
            actor_details=_maintenance_actor_details(actor),
        )
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _append_privileged_api_audit(
        actor=actor,
        action="postgres-cutover-rehearsal",
        target=request.target_database_url,
        outcome=summary.status,
    )
    return PostgresCutoverRehearsalResponse(**summary.to_dict())


@app.post(
    "/maintenance/control-plane-cutover-readiness",
    response_model=ControlPlaneCutoverReadinessResponse,
    dependencies=[Depends(require_api_key)],
)
async def evaluate_control_plane_cutover_readiness(
    request: EvaluateControlPlaneCutoverReadinessRequest,
) -> ControlPlaneCutoverReadinessResponse:
    try:
        summary = _control_plane_cutover_readiness_service().evaluate(
            target_database_url=request.target_database_url,
            package_dir=request.package_dir,
            rehearsal_max_age_hours=request.rehearsal_max_age_hours,
            require_apply_rehearsal=request.require_apply_rehearsal,
            require_runtime_validation=request.require_runtime_validation,
            require_live_workload_target_validation=request.require_live_workload_target_validation,
            require_live_workload_proof_validation=request.require_live_workload_proof_validation,
            require_backup_validation=request.require_backup_validation,
        )
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ControlPlaneCutoverReadinessResponse(**summary.to_dict())


@app.post(
    "/maintenance/control-plane-cutover-decision",
    response_model=ControlPlaneCutoverPromotionResponse,
    dependencies=[Depends(require_api_key)],
)
async def decide_control_plane_cutover(
    request: DecideControlPlaneCutoverRequest,
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> ControlPlaneCutoverPromotionResponse:
    try:
        summary = _control_plane_cutover_promotion_service().decide(
            target_database_url=request.target_database_url,
            package_dir=request.package_dir,
            changed_by=actor.actor_id,
            requested_decision=request.requested_decision,
            reason=request.reason,
            decision_note=request.decision_note,
            rehearsal_max_age_hours=request.rehearsal_max_age_hours,
            require_apply_rehearsal=request.require_apply_rehearsal,
            require_runtime_validation=request.require_runtime_validation,
            require_live_workload_target_validation=request.require_live_workload_target_validation,
            require_live_workload_proof_validation=request.require_live_workload_proof_validation,
            require_backup_validation=request.require_backup_validation,
            allow_override=request.allow_override,
            actor_details=_maintenance_actor_details(actor),
        )
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _append_privileged_api_audit(
        actor=actor,
        action="control-plane-cutover-decision",
        target=request.target_database_url,
        outcome=summary.final_decision,
    )
    return ControlPlaneCutoverPromotionResponse(**summary.to_dict())


@app.get("/snapshots", response_model=list[SnapshotRecordPayload], dependencies=[Depends(require_api_key), Depends(require_reports_actor)])
async def list_snapshots() -> list[SnapshotRecordPayload]:
    return [SnapshotRecordPayload(**record.to_dict()) for record in snapshot_repository.list()]


@app.get("/snapshots/{snapshot_id}", response_model=SnapshotRecordPayload, dependencies=[Depends(require_api_key), Depends(require_reports_actor)])
async def get_snapshot(snapshot_id: str) -> SnapshotRecordPayload:
    try:
        record = snapshot_repository.get(snapshot_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Snapshot '{snapshot_id}' was not found.") from exc
    return SnapshotRecordPayload(**record.to_dict())


@app.get("/audits", response_model=list[AuditRecordPayload], dependencies=[Depends(require_api_key), Depends(require_reports_actor)])
async def list_audits() -> list[AuditRecordPayload]:
    return [AuditRecordPayload(**record.to_dict()) for record in audit_repository.list()]


@app.get("/audits/{audit_id}", response_model=AuditRecordPayload, dependencies=[Depends(require_api_key), Depends(require_reports_actor)])
async def get_audit(audit_id: str) -> AuditRecordPayload:
    try:
        record = audit_repository.get(audit_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Audit '{audit_id}' was not found.") from exc
    return AuditRecordPayload(**record.to_dict())


@app.get("/remediation-reports", response_model=list[RemediationIndexRecordPayload], dependencies=[Depends(require_api_key), Depends(require_reports_actor)])
async def list_remediation_reports(
    limit: int = Query(default=100, ge=1, le=1000),
    function: str | None = Query(default=None),
    risk: str | None = Query(default=None),
    environment_name: str | None = Query(default=None),
) -> list[RemediationIndexRecordPayload]:
    return [
        RemediationIndexRecordPayload(**record.to_dict())
        for record in remediation_index_service.list_reports(
            limit=limit,
            function=function,
            risk=risk,
            environment_name=environment_name,
        )
    ]


@app.get("/jobs", response_model=list[JobRecordPayload], dependencies=[Depends(require_api_key)])
async def list_jobs() -> list[JobRecordPayload]:
    return [JobRecordPayload(**record.to_dict()) for record in job_service.list_jobs()]


@app.get("/jobs/{job_id}", response_model=JobRecordPayload, dependencies=[Depends(require_api_key)])
async def get_job(job_id: str) -> JobRecordPayload:
    try:
        record = job_service.get_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' was not found.") from exc
    return JobRecordPayload(**record.to_dict())


@app.get("/jobs/{job_id}/lease-events", response_model=list[JobLeaseEventPayload], dependencies=[Depends(require_api_key)])
async def list_job_lease_events(job_id: str) -> list[JobLeaseEventPayload]:
    try:
        job_service.get_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' was not found.") from exc
    return [JobLeaseEventPayload(**record.to_dict()) for record in job_service.list_job_lease_events(job_id)]


@app.get("/jobs/{job_id}/lease-event-rollups", response_model=list[JobLeaseEventRollupPayload], dependencies=[Depends(require_api_key)])
async def list_job_lease_event_rollups(job_id: str) -> list[JobLeaseEventRollupPayload]:
    try:
        job_service.get_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' was not found.") from exc
    return [JobLeaseEventRollupPayload(**record.to_dict()) for record in job_repository.list_job_lease_event_rollups(job_id)]


@app.get("/workers", response_model=list[WorkerRecordPayload], dependencies=[Depends(require_api_key)])
async def list_workers() -> list[WorkerRecordPayload]:
    return [WorkerRecordPayload(**record.to_dict()) for record in job_service.list_workers()]


@app.get("/workers/{worker_id}", response_model=WorkerRecordPayload, dependencies=[Depends(require_api_key)])
async def get_worker(worker_id: str) -> WorkerRecordPayload:
    try:
        record = job_service.get_worker(worker_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Worker '{worker_id}' was not found.") from exc
    return WorkerRecordPayload(**record.to_dict())


@app.get("/workers/{worker_id}/heartbeats", response_model=list[WorkerHeartbeatPayload], dependencies=[Depends(require_api_key)])
async def list_worker_heartbeats(worker_id: str) -> list[WorkerHeartbeatPayload]:
    try:
        job_service.get_worker(worker_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Worker '{worker_id}' was not found.") from exc
    return [WorkerHeartbeatPayload(**record.to_dict()) for record in job_service.list_worker_heartbeats(worker_id)]


@app.get("/workers/{worker_id}/heartbeat-rollups", response_model=list[WorkerHeartbeatRollupPayload], dependencies=[Depends(require_api_key)])
async def list_worker_heartbeat_rollups(worker_id: str) -> list[WorkerHeartbeatRollupPayload]:
    try:
        job_service.get_worker(worker_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Worker '{worker_id}' was not found.") from exc
    return [WorkerHeartbeatRollupPayload(**record.to_dict()) for record in job_repository.list_worker_heartbeat_rollups(worker_id)]


@app.post("/maintenance/prune-history", response_model=PruneHistoryResponse, dependencies=[Depends(require_api_key)])
async def prune_history(
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> PruneHistoryResponse:
    result = job_service.prune_history(force=True)
    _append_privileged_api_audit(
        actor=actor,
        action="prune-history",
        target="control-plane-history",
        outcome="ok",
    )
    return PruneHistoryResponse(**result)


@app.get(
    "/maintenance/control-plane-schema/contract",
    response_model=ControlPlaneSchemaContractResponse,
    dependencies=[Depends(require_api_key)],
)
async def get_control_plane_schema_contract() -> ControlPlaneSchemaContractResponse:
    return ControlPlaneSchemaContractResponse(**job_repository.schema_contract())


@app.get(
    "/maintenance/control-plane-schema",
    response_model=ControlPlaneSchemaStatusResponse,
    dependencies=[Depends(require_api_key)],
)
async def get_control_plane_schema_status() -> ControlPlaneSchemaStatusResponse:
    return ControlPlaneSchemaStatusResponse(**job_repository.schema_status())


@app.post(
    "/maintenance/control-plane-schema/migrate",
    response_model=ControlPlaneSchemaStatusResponse,
    dependencies=[Depends(require_api_key)],
)
async def migrate_control_plane_schema(
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> ControlPlaneSchemaStatusResponse:
    result = job_repository.migrate_schema()
    job_service.record_maintenance_event(
        event_type="schema_migrated",
        changed_by=actor.actor_id,
        details=result,
        actor_details=_maintenance_actor_details(actor),
    )
    _append_privileged_api_audit(
        actor=actor,
        action="schema-migrate",
        target="control-plane-schema",
        outcome="ok",
        details=_privileged_audit_details(actor),
    )
    return ControlPlaneSchemaStatusResponse(**result)


@app.post(
    "/maintenance/export-control-plane-backup",
    response_model=ControlPlaneBackupResponse,
    dependencies=[Depends(require_api_key)],
)
async def export_control_plane_backup(
    request: ExportControlPlaneBackupRequest,
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> ControlPlaneBackupResponse:
    summary = control_plane_backup_service.export_bundle(request.output_path)
    job_service.record_maintenance_event(
        event_type="backup_exported",
        changed_by=actor.actor_id,
        details=summary.to_dict(),
        actor_details=_maintenance_actor_details(actor),
    )
    _append_privileged_api_audit(
        actor=actor,
        action="backup-export",
        target="control-plane-backup",
        outcome="ok",
        details=_privileged_audit_details(actor, output_path=request.output_path),
    )
    return ControlPlaneBackupResponse(**summary.to_dict())


@app.post(
    "/maintenance/import-control-plane-backup",
    response_model=ControlPlaneBackupResponse,
    dependencies=[Depends(require_api_key)],
)
async def import_control_plane_backup(
    request: ImportControlPlaneBackupRequest,
    actor: ControlPlaneActor = Depends(require_admin_actor),
) -> ControlPlaneBackupResponse:
    try:
        summary = control_plane_backup_service.import_bundle(
            request.input_path,
            replace_existing=request.replace_existing,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    job_service.record_maintenance_event(
        event_type="backup_imported",
        changed_by=actor.actor_id,
        details=summary.to_dict(),
        actor_details=_maintenance_actor_details(actor),
    )
    _append_privileged_api_audit(
        actor=actor,
        action="backup-import",
        target="control-plane-backup",
        outcome="ok",
        details=_privileged_audit_details(
            actor,
            input_path=request.input_path,
            replace_existing=request.replace_existing,
        ),
    )
    return ControlPlaneBackupResponse(**summary.to_dict())


@app.post(
    "/maintenance/emit-control-plane-alerts",
    response_model=EmitControlPlaneAlertsResponse,
    dependencies=[Depends(require_api_key)],
)
async def emit_control_plane_alerts(
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> EmitControlPlaneAlertsResponse:
    alerts = job_service.emit_control_plane_alerts(force=True)
    _append_privileged_api_audit(
        actor=actor,
        action="emit-control-plane-alerts",
        target="control-plane-alerts",
        outcome=str(len(alerts)),
    )
    return EmitControlPlaneAlertsResponse(
        emitted_count=len(alerts),
        alerts=[ControlPlaneAlertRecordPayload(**record.to_dict()) for record in alerts],
    )


@app.post(
    "/maintenance/process-control-plane-alert-followups",
    response_model=EmitControlPlaneAlertsResponse,
    dependencies=[Depends(require_api_key)],
)
async def process_control_plane_alert_followups(
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> EmitControlPlaneAlertsResponse:
    alerts = job_service.process_control_plane_alert_follow_ups(force=True)
    _append_privileged_api_audit(
        actor=actor,
        action="process-control-plane-alert-followups",
        target="control-plane-alerts",
        outcome=str(len(alerts)),
    )
    return EmitControlPlaneAlertsResponse(
        emitted_count=len(alerts),
        alerts=[ControlPlaneAlertRecordPayload(**record.to_dict()) for record in alerts],
    )


@app.get(
    "/analytics/control-plane",
    response_model=ControlPlaneAnalyticsResponse,
    dependencies=[Depends(require_api_key), Depends(require_reports_actor)],
)
async def get_control_plane_analytics(days: int = Query(default=30, ge=1, le=365)) -> ControlPlaneAnalyticsResponse:
    report = analytics_service.build_control_plane_analytics(days=days)
    return ControlPlaneAnalyticsResponse(**report.to_dict())


@app.get(
    "/control-plane-alerts",
    response_model=list[ControlPlaneAlertRecordPayload],
    dependencies=[Depends(require_api_key), Depends(require_reports_actor)],
)
async def list_control_plane_alerts(
    limit: int = Query(default=50, ge=1, le=500),
    actor: ControlPlaneActor = Depends(require_reports_actor),
) -> list[ControlPlaneAlertRecordPayload]:
    return [
        ControlPlaneAlertRecordPayload(**record.to_dict())
        for record in job_service.list_control_plane_alerts_scoped(
            actor=_authorized_actor(actor),
            limit=limit,
        )
    ]


@app.post(
    "/control-plane-alerts/{alert_id}/acknowledge",
    response_model=ControlPlaneAlertRecordPayload,
    dependencies=[Depends(require_api_key), Depends(require_control_plane_mutation_allowed)],
)
async def acknowledge_control_plane_alert(
    alert_id: str,
    request: AcknowledgeControlPlaneAlertRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneAlertRecordPayload:
    try:
        record = job_service.acknowledge_control_plane_alert_scoped(
            actor=_authorized_actor(actor),
            alert_id=alert_id,
            acknowledged_by=actor.actor_id,
            acknowledgement_note=request.acknowledgement_note,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Control-plane alert '{alert_id}' was not found.") from exc
    return ControlPlaneAlertRecordPayload(**record.to_dict())


@app.get(
    "/control-plane-alert-silences",
    response_model=list[ControlPlaneAlertSilencePayload],
    dependencies=[Depends(require_api_key)],
)
async def list_control_plane_alert_silences(
    active_only: bool = Query(default=False),
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> list[ControlPlaneAlertSilencePayload]:
    return [
        ControlPlaneAlertSilencePayload(**record.to_dict())
        for record in job_service.list_control_plane_alert_silences_scoped(
            actor=_authorized_actor(actor),
            active_only=active_only,
        )
    ]


@app.post(
    "/control-plane-alert-silences",
    response_model=ControlPlaneAlertSilencePayload,
    dependencies=[Depends(require_api_key), Depends(require_control_plane_mutation_allowed)],
)
async def create_control_plane_alert_silence(
    request: CreateControlPlaneAlertSilenceRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneAlertSilencePayload:
    record = job_service.create_control_plane_alert_silence_scoped(
        actor=_authorized_actor(actor),
        created_by=actor.actor_id,
        reason=request.reason,
        duration_minutes=request.duration_minutes,
        match_alert_key=request.match_alert_key,
        match_finding_code=request.match_finding_code,
    )
    return ControlPlaneAlertSilencePayload(**record.to_dict())


@app.post(
    "/control-plane-alert-silences/{silence_id}/cancel",
    response_model=ControlPlaneAlertSilencePayload,
    dependencies=[Depends(require_api_key), Depends(require_control_plane_mutation_allowed)],
)
async def cancel_control_plane_alert_silence(
    silence_id: str,
    request: CancelControlPlaneAlertSilenceRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneAlertSilencePayload:
    try:
        record = job_service.cancel_control_plane_alert_silence_scoped(
            actor=_authorized_actor(actor),
            silence_id=silence_id,
            cancelled_by=actor.actor_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Control-plane alert silence '{silence_id}' was not found.") from exc
    return ControlPlaneAlertSilencePayload(**record.to_dict())


@app.get(
    "/control-plane-oncall-change-requests",
    response_model=list[ControlPlaneOnCallChangeRequestPayload],
    dependencies=[Depends(require_api_key)],
)
async def list_control_plane_oncall_change_requests(
    status: str | None = Query(default=None),
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> list[ControlPlaneOnCallChangeRequestPayload]:
    records = control_plane_alert_service.list_oncall_change_requests_scoped(
        actor=_authorized_actor(actor),
        status=status,
    )
    return [ControlPlaneOnCallChangeRequestPayload(**record.to_dict()) for record in records]


@app.get(
    "/control-plane-oncall-change-requests/{request_id}",
    response_model=ControlPlaneOnCallChangeRequestPayload,
    dependencies=[Depends(require_api_key)],
)
async def get_control_plane_oncall_change_request(
    request_id: str,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneOnCallChangeRequestPayload:
    try:
        record = control_plane_alert_service.get_oncall_change_request_scoped(
            actor=_authorized_actor(actor),
            request_id=request_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Control-plane on-call change request '{request_id}' was not found.",
        ) from exc
    return ControlPlaneOnCallChangeRequestPayload(**record.to_dict())


@app.post(
    "/control-plane-oncall-change-requests",
    response_model=ControlPlaneOnCallChangeRequestPayload,
    dependencies=[Depends(require_api_key), Depends(require_control_plane_mutation_allowed)],
)
async def create_control_plane_oncall_change_request(
    request: CreateControlPlaneOnCallChangeRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneOnCallChangeRequestPayload:
    try:
        record = control_plane_alert_service.submit_oncall_change_request_scoped(
            actor=_authorized_actor(actor),
            created_by=actor.actor_id,
            environment_name=request.environment_name,
            created_by_team=request.created_by_team,
            created_by_role=actor.role,
            change_reason=request.change_reason,
            team_name=request.team_name,
            timezone_name=request.timezone_name,
            weekdays=request.weekdays,
            start_time=request.start_time,
            end_time=request.end_time,
            priority=request.priority,
            rotation_name=request.rotation_name,
            effective_start_date=request.effective_start_date,
            effective_end_date=request.effective_end_date,
            webhook_url=request.webhook_url,
            escalation_webhook_url=request.escalation_webhook_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ControlPlaneOnCallChangeRequestPayload(**record.to_dict())


@app.post(
    "/control-plane-oncall-change-requests/{request_id}/assign",
    response_model=ControlPlaneOnCallChangeRequestPayload,
    dependencies=[Depends(require_api_key), Depends(require_control_plane_mutation_allowed)],
)
async def assign_control_plane_oncall_change_request(
    request_id: str,
    request: AssignControlPlaneOnCallChangeRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneOnCallChangeRequestPayload:
    try:
        record = control_plane_alert_service.assign_oncall_change_request_scoped(
            actor=_authorized_actor(actor),
            request_id=request_id,
            assigned_to=request.assigned_to,
            assigned_to_team=request.assigned_to_team,
            assigned_by=actor.actor_id,
            assignment_note=request.assignment_note,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Control-plane on-call change request '{request_id}' was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ControlPlaneOnCallChangeRequestPayload(**record.to_dict())


@app.post(
    "/control-plane-oncall-change-requests/{request_id}/review",
    response_model=ControlPlaneOnCallChangeRequestPayload,
    dependencies=[Depends(require_api_key), Depends(require_control_plane_mutation_allowed)],
)
async def review_control_plane_oncall_change_request(
    request_id: str,
    request: ReviewControlPlaneOnCallChangeRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneOnCallChangeRequestPayload:
    try:
        record = control_plane_alert_service.review_oncall_change_request_scoped(
            actor=_authorized_actor(actor),
            request_id=request_id,
            decision=request.decision,
            reviewed_by=actor.actor_id,
            reviewed_by_team=request.reviewed_by_team,
            reviewed_by_role=actor.role,
            review_note=request.review_note,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Control-plane on-call change request '{request_id}' was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ControlPlaneOnCallChangeRequestPayload(**record.to_dict())


@app.get(
    "/control-plane-oncall-schedules",
    response_model=list[ControlPlaneOnCallSchedulePayload],
    dependencies=[Depends(require_api_key)],
)
async def list_control_plane_oncall_schedules(
    active_only: bool = Query(default=False),
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> list[ControlPlaneOnCallSchedulePayload]:
    records = control_plane_alert_service.list_oncall_schedules_scoped(
        actor=_authorized_actor(actor),
        active_only=active_only,
    )
    return [ControlPlaneOnCallSchedulePayload(**record.to_dict()) for record in records]


@app.get(
    "/control-plane-oncall-schedules/resolve",
    response_model=ControlPlaneOnCallRouteResolutionPayload,
    dependencies=[Depends(require_api_key)],
)
async def resolve_control_plane_oncall_schedule(
    at: str | None = Query(default=None),
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneOnCallRouteResolutionPayload:
    preview = control_plane_alert_service.preview_oncall_route_scoped(
        actor=_authorized_actor(actor),
        reference_timestamp=_parse_timestamp_query(at),
    )
    return ControlPlaneOnCallRouteResolutionPayload(**preview)


@app.post(
    "/control-plane-oncall-schedules",
    response_model=ControlPlaneOnCallSchedulePayload,
    dependencies=[Depends(require_api_key), Depends(require_control_plane_mutation_allowed)],
)
async def create_control_plane_oncall_schedule(
    request: CreateControlPlaneOnCallScheduleRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneOnCallSchedulePayload:
    try:
        record = control_plane_alert_service.create_oncall_schedule_scoped(
            actor=_authorized_actor(actor),
            created_by=actor.actor_id,
            environment_name=request.environment_name,
            created_by_team=request.created_by_team,
            created_by_role=actor.role,
            change_reason=request.change_reason,
            approved_by=actor.actor_id if request.approved_by else None,
            approved_by_team=request.approved_by_team,
            approved_by_role=actor.role if request.approved_by_role or request.approved_by else None,
            approval_note=request.approval_note,
            team_name=request.team_name,
            timezone_name=request.timezone_name,
            weekdays=request.weekdays,
            start_time=request.start_time,
            end_time=request.end_time,
            priority=request.priority,
            rotation_name=request.rotation_name,
            effective_start_date=request.effective_start_date,
            effective_end_date=request.effective_end_date,
            webhook_url=request.webhook_url,
            escalation_webhook_url=request.escalation_webhook_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ControlPlaneOnCallSchedulePayload(**record.to_dict())


@app.post(
    "/control-plane-oncall-schedules/{schedule_id}/cancel",
    response_model=ControlPlaneOnCallSchedulePayload,
    dependencies=[Depends(require_api_key), Depends(require_control_plane_mutation_allowed)],
)
async def cancel_control_plane_oncall_schedule(
    schedule_id: str,
    request: CancelControlPlaneOnCallScheduleRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> ControlPlaneOnCallSchedulePayload:
    try:
        record = control_plane_alert_service.cancel_oncall_schedule_scoped(
            actor=_authorized_actor(actor),
            schedule_id=schedule_id,
            cancelled_by=actor.actor_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Control-plane on-call schedule '{schedule_id}' was not found.") from exc
    return ControlPlaneOnCallSchedulePayload(**record.to_dict())


@app.post(
    "/ingest",
    response_model=IngestResponse,
    dependencies=[Depends(require_api_key), Depends(require_control_plane_mutation_allowed)],
)
async def ingest_codebase(
    request: IngestRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> IngestResponse:
    result = ingest_service.ingest(
        request.repo_path,
        persist=request.persist,
        output_path=request.output_path,
        snapshot_id=request.snapshot_id,
    )
    _append_privileged_api_audit(
        actor=actor,
        action="ingest",
        target=request.repo_path,
        outcome=result.record.snapshot_id if result.record else "ok",
    )
    return IngestResponse(
        node_count=result.snapshot.node_count,
        edge_count=result.snapshot.edge_count,
        snapshot_path=result.snapshot_path,
        snapshot_id=result.record.snapshot_id if result.record else None,
        created_at=result.record.created_at if result.record else None,
    )


@app.post(
    "/audit",
    response_model=AuditResponse,
    dependencies=[Depends(require_api_key), Depends(require_control_plane_mutation_allowed)],
)
async def audit_runtime(
    request: AuditRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> AuditResponse:
    try:
        result = audit_service.audit(
            snapshot_id=request.snapshot_id,
            snapshot_path=request.snapshot_path,
            events=[ObservedEvent.from_dict(item.model_dump()) for item in request.events],
            persist=request.persist,
            report_dir=request.report_dir,
            audit_id=request.audit_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Snapshot reference could not be resolved.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _append_privileged_api_audit(
        actor=actor,
        action="audit",
        target=request.snapshot_id or request.snapshot_path or "snapshot",
        outcome=result.record.audit_id if result.record else "ok",
    )
    return AuditResponse(
        alert_count=len(result.alerts),
        report_paths=result.report_paths,
        alerts=[alert.to_dict() for alert in result.alerts],
        sessions=[session.to_dict() for session in result.sessions],
        explanation=result.explanation.to_dict(),
        audit_id=result.record.audit_id if result.record else None,
        snapshot_id=result.snapshot_record.snapshot_id if result.snapshot_record else None,
        snapshot_path=result.snapshot_path or "",
    )


@app.post(
    "/audit-trace",
    response_model=AuditResponse,
    dependencies=[Depends(require_api_key), Depends(require_control_plane_mutation_allowed)],
)
async def audit_trace(
    request: AuditTraceRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> AuditResponse:
    try:
        trace_events = load_trace_events(request.trace_path, trace_format=request.trace_format)
        result = audit_service.audit(
            snapshot_id=request.snapshot_id,
            snapshot_path=request.snapshot_path,
            events=trace_events,
            persist=request.persist,
            report_dir=request.report_dir,
            audit_id=request.audit_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Snapshot or trace path could not be resolved.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _append_privileged_api_audit(
        actor=actor,
        action="audit-trace",
        target=request.trace_path,
        outcome=result.record.audit_id if result.record else "ok",
    )
    return AuditResponse(
        alert_count=len(result.alerts),
        report_paths=result.report_paths,
        alerts=[alert.to_dict() for alert in result.alerts],
        sessions=[session.to_dict() for session in result.sessions],
        explanation=result.explanation.to_dict(),
        audit_id=result.record.audit_id if result.record else None,
        snapshot_id=result.snapshot_record.snapshot_id if result.snapshot_record else None,
        snapshot_path=result.snapshot_path or "",
    )


@app.post(
    "/jobs/audit-trace",
    response_model=JobRecordPayload,
    status_code=202,
    dependencies=[Depends(require_api_key), Depends(require_control_plane_mutation_allowed)],
)
async def submit_audit_trace_job(
    request: AuditTraceRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> JobRecordPayload:
    job = job_service.submit_audit_trace(request.model_dump())
    _append_privileged_api_audit(
        actor=actor,
        action="submit-audit-trace-job",
        target=request.trace_path,
        outcome=job.job_id,
    )
    return JobRecordPayload(**job.to_dict())


@app.post(
    "/collect-trace",
    response_model=CollectTraceResponse,
    dependencies=[Depends(require_api_key), Depends(require_control_plane_mutation_allowed)],
)
async def collect_trace(
    request: CollectTraceRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> CollectTraceResponse:
    try:
        result = trace_collection_service.collect(_build_trace_collection_request(request))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Collector program or symbol map path could not be resolved.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _append_privileged_api_audit(
        actor=actor,
        action="collect-trace",
        target=request.program,
        outcome=result.trace_path,
    )
    return CollectTraceResponse(
        command=result.command,
        trace_path=result.trace_path,
        trace_metadata_path=result.metadata_path,
        trace_symbol_map_path=result.symbol_map_path,
        trace_context_map_path=result.context_map_path,
        line_count=result.line_count,
        return_code=result.return_code,
    )


@app.post(
    "/jobs/collect-audit",
    response_model=JobRecordPayload,
    status_code=202,
    dependencies=[Depends(require_api_key), Depends(require_control_plane_mutation_allowed)],
)
async def submit_collect_audit_job(
    request: CollectAuditRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> JobRecordPayload:
    job = job_service.submit_collect_audit(request.model_dump())
    _append_privileged_api_audit(
        actor=actor,
        action="submit-collect-audit-job",
        target=request.program,
        outcome=job.job_id,
    )
    return JobRecordPayload(**job.to_dict())


@app.post(
    "/collect-audit",
    response_model=CollectAuditResponse,
    dependencies=[Depends(require_api_key), Depends(require_control_plane_mutation_allowed)],
)
async def collect_audit(
    request: CollectAuditRequest,
    actor: ControlPlaneActor = Depends(require_operator_actor),
) -> CollectAuditResponse:
    try:
        observation = trace_collection_service.collect(_build_trace_collection_request(request))
        result = audit_service.audit(
            snapshot_id=request.snapshot_id,
            snapshot_path=request.snapshot_path,
            events=load_trace_events(observation.trace_path, trace_format=request.trace_format),
            persist=request.persist,
            audit_id=request.audit_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Snapshot, collector program, trace, or symbol map path could not be resolved.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _append_privileged_api_audit(
        actor=actor,
        action="collect-audit",
        target=request.program,
        outcome=result.record.audit_id if result.record else "ok",
    )
    return CollectAuditResponse(
        trace_path=observation.trace_path,
        trace_metadata_path=observation.metadata_path,
        trace_symbol_map_path=observation.symbol_map_path,
        trace_context_map_path=observation.context_map_path,
        line_count=observation.line_count,
        alert_count=len(result.alerts),
        report_paths=result.report_paths,
        alerts=[alert.to_dict() for alert in result.alerts],
        sessions=[session.to_dict() for session in result.sessions],
        explanation=result.explanation.to_dict(),
        audit_id=result.record.audit_id if result.record else None,
        snapshot_id=result.snapshot_record.snapshot_id if result.snapshot_record else None,
        snapshot_path=result.snapshot_path or "",
    )


def _build_trace_collection_request(
    request: CollectTraceRequest | CollectAuditRequest,
) -> TraceCollectionRequest:
    return TraceCollectionRequest(
        pid=request.pid,
        program_path=request.program,
        output_path=request.output_path,
        duration_seconds=request.duration,
        max_events=request.max_events,
        symbol_map_path=request.symbol_map_path,
        context_map_path=request.context_map_path,
        command=None if request.program.endswith(".bt") else ["/bin/sh", request.program],
    )
