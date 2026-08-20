export type HealthResponse = {
  status: string;
  service: string;
  environment_name: string;
  organization_name?: string | null;
  auth_required?: boolean;
  authz_enabled?: boolean;
  database_backend?: string;
  database_ready?: boolean;
  database_schema_ready?: boolean;
  worker_mode?: string;
  worker_running?: boolean;
  active_workers?: number;
  queued_jobs?: number;
  running_jobs?: number;
  deployment_readiness_ready?: boolean;
  runtime_validation_status?: string;
  live_workload_target_status?: string;
  live_workload_target_cadence_status?: string;
  live_workload_proof_status?: string;
  backup_validation_status?: string;
  backup_export_validation_status?: string;
  observability_export_validation_status?: string;
  operational_validation_status?: string;
  soak_validation_status?: string;
};

export type RuntimeValidationResponse = {
  generated_at: string;
  environment_name: string;
  status: string;
  severity: string;
  cadence_status: string;
  policy_source: string;
  age_hours?: number | null;
  due_in_hours?: number | null;
  blockers: string[];
};

export type TargetValidationResponse = {
  generated_at: string;
  status: string;
  severity: string;
  cadence_status: string;
  warning_age_hours: number;
  critical_age_hours: number;
  due_soon_age_hours?: number;
  latest_validation_recorded_at?: string | null;
  latest_target_profile?: string | null;
  latest_target_mode?: string | null;
  age_hours?: number | null;
  due_in_hours?: number | null;
  blockers: string[];
};

export type ProofValidationResponse = {
  generated_at: string;
  status: string;
  severity: string;
  cadence_status?: string;
  latest_proof_recorded_at?: string | null;
  latest_target_profile?: string | null;
  latest_event_count?: number | null;
  latest_alert_count?: number | null;
  age_hours?: number | null;
  due_in_hours?: number | null;
  blockers: string[];
};

export type BackupValidationResponse = {
  generated_at: string;
  status: string;
  severity: string;
  latest_backup_created_at?: string | null;
  age_hours?: number | null;
  blockers: string[];
};

export type ExportValidationResponse = {
  generated_at: string;
  status: string;
  severity: string;
  latest_exported_at?: string | null;
  age_hours?: number | null;
  blockers: string[];
};

export type ReadinessResponse = {
  evaluated_at: string;
  environment_name: string;
  runtime_validation: RuntimeValidationResponse;
  live_workload_target_validation: TargetValidationResponse;
  live_workload_proof_validation: ProofValidationResponse;
  backup_validation: BackupValidationResponse;
  backup_export_validation: ExportValidationResponse;
  observability_export_validation: ExportValidationResponse;
  runtime_validation_change_control_requests: ChangeControlRequest[];
  owner_team_rollups: Array<Record<string, unknown>>;
  blocked_owner_team_count: number;
  oldest_rejected_age_hours?: number | null;
  blockers: string[];
  warnings: string[];
  ready: boolean;
};

export type Finding = {
  severity: string;
  code: string;
  metric: string;
  summary: string;
  observed_value: number;
  threshold_value?: number | null;
};

export type RuntimeReview = {
  review_id: string;
  opened_at: string;
  opened_by: string;
  status: string;
  summary: string;
  trigger_status: string;
  trigger_cadence_status: string;
  owner_team?: string | null;
  assigned_to?: string | null;
  assigned_to_team?: string | null;
  due_in_hours?: number | null;
  policy_source: string;
};

export type RuntimeReviewQueue = {
  environment_name: string;
  total_reviews: number;
  assigned_reviews: number;
  unassigned_reviews: number;
  stale_reviews: number;
  stale_unassigned_reviews: number;
  oldest_review_age_hours?: number | null;
  owner_team_rollups: Array<{
    owner_team: string;
    total_reviews: number;
    assigned_reviews: number;
    unassigned_reviews: number;
    stale_reviews: number;
  }>;
  reviews: RuntimeReview[];
};

export type ChangeControlRequest = {
  request_id: string;
  opened_at: string;
  opened_by: string;
  owner_team?: string | null;
  summary: string;
  status: string;
  trigger_code: string;
  assigned_to?: string | null;
  assigned_to_team?: string | null;
  resolved_at?: string | null;
  resolution_reason?: string | null;
};

export type OwnerTeamQueue = {
  environment_name: string;
  total_requests: number;
  assigned_requests: number;
  unassigned_requests: number;
  pending_review_count: number;
  rejected_count: number;
  owner_team_rollups: Array<Record<string, unknown>>;
  requests: ChangeControlRequest[];
};

export type AlertRecord = {
  alert_id: string;
  alert_key: string;
  status: string;
  severity: string;
  summary: string;
  finding_codes?: string[];
  created_at: string;
  last_emitted_at?: string | null;
  acknowledged_at?: string | null;
  acknowledged_by?: string | null;
  owner_team?: string | null;
  delivery_state?: string;
};

export type AnalyticsResponse = {
  generated_at: string;
  window_days: number;
  runtime_validation: RuntimeValidationResponse;
  live_workload_target_validation: TargetValidationResponse;
  live_workload_proof_validation: ProofValidationResponse;
  deployment_readiness: {
    ready: boolean;
    blocker_count: number;
    warning_count: number;
    pending_change_control_count: number;
    rejected_change_control_count: number;
    blocked_owner_team_count: number;
    oldest_rejected_age_hours?: number | null;
    blockers: string[];
    warnings: string[];
  };
  runtime_validation_reviews: {
    total_active_reviews: number;
    assigned_reviews: number;
    unassigned_reviews: number;
    stale_reviews: number;
    stale_unassigned_reviews: number;
    owner_team_rollups: Array<Record<string, unknown>>;
    sample_reviews: RuntimeReview[];
  };
  privileged_api_audit: {
    recent_entries: number;
    non_ok_recent_entries: number;
    denied_recent_entries: number;
    blocked_recent_entries: number;
    rejected_recent_entries: number;
    top_actions: Array<Record<string, unknown>>;
  };
  evaluation: {
    status: string;
    findings: Finding[];
  };
};

export type TrustScoreFactor = {
  code: string;
  label: string;
  impact: number;
  status: string;
  summary: string;
  context: Record<string, unknown>;
};

export type TrustScoreResponse = {
  generated_at: string;
  environment_name: string;
  score: number;
  grade: string;
  status: string;
  factors: TrustScoreFactor[];
};

export type IncidentNarrativeTimelineEntry = {
  recorded_at: string;
  source_type: string;
  source_id: string;
  title: string;
  summary: string;
  severity?: string | null;
};

export type IncidentNarrativeResponse = {
  generated_at: string;
  environment_name: string;
  headline: string;
  status: string;
  summary: string;
  likely_causes: string[];
  immediate_actions: string[];
  timeline: IncidentNarrativeTimelineEntry[];
};

export type RuntimeActionResponse = {
  validation_id?: string;
  rehearsal_id?: string;
  status?: string;
  checks?: Record<string, boolean>;
  emitted_count?: number;
};

export type CanaryVerifierResponse = {
  verification_id: string;
  executed_at: string;
  changed_by: string;
  reason?: string | null;
  environment_name: string;
  target_profile_name: string;
  expected_backend: string;
  target_validation: Record<string, unknown>;
  drift_proof: Record<string, unknown>;
  operational_validation: Record<string, unknown>;
  checks: Record<string, boolean>;
  blockers: string[];
  verdict: string;
  recommended_action: string;
  maintenance_event_id?: string | null;
};

export type TargetProfile = {
  name: string;
  approved_target_base_url: string;
  drift_target_base_url: string;
  organization_name?: string | null;
  team_name?: string | null;
  project_name?: string | null;
  environment_name?: string | null;
  approved_probe_url?: string | null;
  drift_probe_url?: string | null;
  approved_action_url?: string | null;
  drift_action_url?: string | null;
  approved_probe_method?: string | null;
  drift_probe_method?: string | null;
  approved_action_method?: string | null;
  drift_action_method?: string | null;
  approved_headers?: Record<string, string> | null;
  drift_headers?: Record<string, string> | null;
  approved_expected_statuses?: number[] | null;
  drift_expected_statuses?: number[] | null;
  request_timeout_seconds?: number | null;
  source: string;
  built_in: boolean;
  enabled: boolean;
  description?: string | null;
};

export type UpsertTargetProfileRequest = {
  name: string;
  approved_target_base_url: string;
  drift_target_base_url: string;
  organization_name?: string | null;
  team_name?: string | null;
  project_name?: string | null;
  environment_name?: string | null;
  approved_probe_url?: string | null;
  drift_probe_url?: string | null;
  approved_action_url?: string | null;
  drift_action_url?: string | null;
  approved_probe_method?: string | null;
  drift_probe_method?: string | null;
  approved_action_method?: string | null;
  drift_action_method?: string | null;
  approved_headers?: Record<string, string> | null;
  drift_headers?: Record<string, string> | null;
  approved_expected_statuses?: number[] | null;
  drift_expected_statuses?: number[] | null;
  request_timeout_seconds?: number | null;
  enabled: boolean;
  description?: string | null;
};

export type DeleteTargetProfileResponse = {
  deleted: boolean;
  profile_name: string;
};

export type TargetActivityEvent = {
  event_id: string;
  recorded_at: string;
  event_type: string;
  category: string;
  changed_by: string;
  reason?: string | null;
  status?: string | null;
  summary?: string | null;
};

export type TargetActivityAlert = {
  alert_id: string;
  created_at: string;
  alert_key: string;
  category: string;
  status: string;
  severity: string;
  summary: string;
};

export type TargetProfileActivity = {
  profile_name: string;
  organization_name?: string | null;
  team_name?: string | null;
  project_name?: string | null;
  environment_name?: string | null;
  latest_validation?: Record<string, unknown> | null;
  latest_drift_proof?: Record<string, unknown> | null;
  latest_canary_verification?: Record<string, unknown> | null;
  latest_operational_validation?: Record<string, unknown> | null;
  event_category_counts: Record<string, number>;
  alert_category_counts: Record<string, number>;
  recent_events: TargetActivityEvent[];
  recent_alerts: TargetActivityAlert[];
};

export type TargetProfileExplanation = {
  profile_name: string;
  status: string;
  source_event_type: string;
  source_event_id?: string | null;
  generated_at: string;
  remediation_provider: string;
  remediation_model?: string | null;
  remediation_available: boolean;
  remediation_fallback_active: boolean;
  title: string;
  summary: string;
  risk: string;
  immediate_action: string;
  long_term_fix: string;
  supporting_facts: string[];
};

export type OrganizationTeam = {
  organization_name: string;
  team_name: string;
  description?: string | null;
  manager_usernames: string[];
  created_at: string;
  updated_at: string;
};

export type OrganizationProject = {
  organization_name: string;
  team_name?: string | null;
  project_name: string;
  description?: string | null;
  created_at: string;
  updated_at: string;
};

export type OrganizationMembership = {
  username: string;
  organization_name: string;
  team_name?: string | null;
  project_name?: string | null;
  role: string;
  status: string;
  granted_by?: string | null;
  granted_at: string;
  updated_at: string;
  note?: string | null;
};

export type OrganizationRemovalEvent = {
  event_id: string;
  username: string;
  organization_name: string;
  team_name?: string | null;
  project_name?: string | null;
  role: string;
  removed_by: string;
  removed_at: string;
  reason: string;
  prior_status: string;
};

export type OrganizationAssignment = {
  assignment_id: string;
  organization_name: string;
  team_name?: string | null;
  project_name?: string | null;
  work_type: string;
  title: string;
  subject_id?: string | null;
  assigned_to?: string | null;
  assigned_by?: string | null;
  status: string;
  details: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type OrganizationAssignmentComment = {
  comment_id: string;
  assignment_id: string;
  organization_name: string;
  team_name?: string | null;
  project_name?: string | null;
  author: string;
  body: string;
  kind: string;
  created_at: string;
};

export type OrganizationWorkspace = {
  organization_name: string;
  teams: OrganizationTeam[];
  projects: OrganizationProject[];
  memberships: OrganizationMembership[];
  removal_events: OrganizationRemovalEvent[];
  assignments: OrganizationAssignment[];
  assignment_comments: OrganizationAssignmentComment[];
};

export type MaintenanceEventRecord = {
  event_id: string;
  recorded_at: string;
  event_type: string;
  changed_by: string;
  reason?: string | null;
  details: Record<string, unknown>;
};

export type OrganizationWorkspaceOperations = {
  organization_name: string;
  team_name?: string | null;
  project_name?: string | null;
  target_profiles: TargetProfile[];
  soak_events: MaintenanceEventRecord[];
};

export type SecretAlias = {
  alias: string;
  env_var_name: string;
  description?: string | null;
  usage_scope?: string | null;
  present: boolean;
  created_at: string;
  updated_at: string;
};

export type DeleteSecretAliasResponse = {
  alias: string;
  deleted: boolean;
};

export type ProofBundleRecord = {
  path: string;
  file_name: string;
  modified_at: string;
  size_bytes: number;
  sha256: string;
};

export type ProofBundleInspection = {
  path: string;
  file_name: string;
  size_bytes: number;
  sha256: string;
  valid: boolean;
  exported_at?: string | null;
  environment_name?: string | null;
  organization_name?: string | null;
  target_profile?: string | null;
  latest_target_validation_event_id?: string | null;
  latest_proof_event_id?: string | null;
  latest_operational_validation_event_id?: string | null;
  blockers: string[];
};

export type ProofBundleExportResponse = {
  exported_at: string;
  environment_name: string;
  target_profile: string;
  output_path: string;
  sha256: string;
  size_bytes: number;
  latest_target_validation_event_id?: string | null;
  latest_proof_event_id?: string | null;
  latest_operational_validation_event_id?: string | null;
};

export type ProofBundleDeleteResponse = {
  deleted_at: string;
  path: string;
  existed: boolean;
};
