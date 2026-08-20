import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";
import { useAuth } from "./auth";

import type {
  AlertRecord,
  AnalyticsResponse,
  CanaryVerifierResponse,
  DeleteTargetProfileResponse,
  HealthResponse,
  IncidentNarrativeResponse,
  SecretAlias,
  DeleteSecretAliasResponse,
  OrganizationWorkspaceOperations,
  OrganizationAssignment,
  OrganizationAssignmentComment,
  OrganizationMembership,
  OrganizationProject,
  OrganizationRemovalEvent,
  OrganizationTeam,
  OrganizationWorkspace,
  OwnerTeamQueue,
  ProofBundleDeleteResponse,
  ProofBundleExportResponse,
  ProofBundleInspection,
  ProofBundleRecord,
  ReadinessResponse,
  RuntimeActionResponse,
  RuntimeReviewQueue,
  TargetProfileActivity,
  TargetProfileExplanation,
  TargetProfile,
  TrustScoreResponse,
  UpsertTargetProfileRequest,
} from "./types";

type ApiConfig = {
  apiKey: string;
  actorId: string;
  actorRole: string;
  actorTeam: string;
  actorOrganization: string;
};

const STORAGE_KEY = "lsa-dashboard-config";
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

const defaultConfig: ApiConfig = {
  apiKey: "",
  actorId: "studio",
  actorRole: "admin",
  actorTeam: "platform",
  actorOrganization: "default",
};

type ApiContextValue = {
  config: ApiConfig;
  updateConfig: (next: Partial<ApiConfig>) => void;
  fetchJson: <T>(path: string, init?: RequestInit) => Promise<T>;
};

const ApiConfigContext = createContext<ApiContextValue | null>(null);

export function ApiConfigProvider({ children }: PropsWithChildren) {
  const { session, logout } = useAuth();
  const [config, setConfig] = useState<ApiConfig>(() => {
    if (typeof window === "undefined") {
      return defaultConfig;
    }
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      return raw ? { ...defaultConfig, ...JSON.parse(raw) } : defaultConfig;
    } catch {
      return defaultConfig;
    }
  });

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
  }, [config]);

  const updateConfig = useCallback((next: Partial<ApiConfig>) => {
    setConfig((current) => ({ ...current, ...next }));
  }, []);

  const fetchJson = useCallback(
    async <T,>(path: string, init: RequestInit = {}) => {
      const headers = new Headers(init.headers || {});
      if (session?.accessToken) {
        headers.set("Authorization", `Bearer ${session.accessToken}`);
      }
      if (config.apiKey) {
        headers.set("X-API-Key", config.apiKey);
      }
      headers.set("X-Actor-Id", session?.username || config.actorId || "studio");
      headers.set("X-Actor-Role", session ? (session.role === "admin" ? "admin" : "operator") : (config.actorRole || "admin"));
      if (config.actorTeam) {
        headers.set("X-Actor-Team", config.actorTeam);
      }
      if (config.actorOrganization) {
        headers.set("X-Actor-Organization", config.actorOrganization);
      }
      if (!headers.has("Content-Type") && init.body) {
        headers.set("Content-Type", "application/json");
      }
      const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
      if (response.status === 401 && session?.accessToken) {
        logout();
      }
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Request failed: ${response.status}`);
      }
      return (await response.json()) as T;
    },
    [config, logout, session],
  );

  const value = useMemo(
    () => ({
      config,
      updateConfig,
      fetchJson,
    }),
    [config, fetchJson, updateConfig],
  );

  return <ApiConfigContext.Provider value={value}>{children}</ApiConfigContext.Provider>;
}

export function useApiConfig() {
  const value = useContext(ApiConfigContext);
  if (!value) {
    throw new Error("ApiConfigContext missing");
  }
  return value;
}

export function useBackendApi() {
  const { fetchJson, config } = useApiConfig();
  const resolveExpectedBackend = async () => {
    const health = await fetchJson<HealthResponse>("/health");
    return health.database_backend || "sqlite";
  };

  return {
    config,
    getHealth: () => fetchJson<HealthResponse>("/health"),
    getReadiness: () =>
      fetchJson<ReadinessResponse>("/maintenance/control-plane-deployment-readiness"),
    getAnalytics: (days = 14) => fetchJson<AnalyticsResponse>(`/analytics/control-plane?days=${days}`),
    getTrustScore: () => fetchJson<TrustScoreResponse>("/maintenance/control-plane-trust-score"),
    getIncidentNarrative: () =>
      fetchJson<IncidentNarrativeResponse>("/maintenance/control-plane-incident-narrative"),
    getRuntimeReviewQueue: () =>
      fetchJson<RuntimeReviewQueue>("/maintenance/control-plane-runtime-validation-review-queue"),
    getOwnerTeamQueue: () =>
      fetchJson<OwnerTeamQueue>("/maintenance/control-plane-deployment-readiness/owner-team-queue"),
    getAlerts: (limit = 12) => fetchJson<AlertRecord[]>(`/control-plane-alerts?limit=${limit}`),
    getTargetProfiles: () =>
      fetchJson<TargetProfile[]>("/maintenance/live-workload-target-profiles"),
    getOrganizationWorkspace: () =>
      fetchJson<OrganizationWorkspace>("/admin/organization-workspace"),
    getOrganizationWorkspaceOperations: (params?: {
      organization_name?: string | null;
      team_name?: string | null;
      project_name?: string | null;
    }) => {
      const query = new URLSearchParams();
      if (params?.organization_name) {
        query.set("organization_name", params.organization_name);
      }
      if (params?.team_name) {
        query.set("team_name", params.team_name);
      }
      if (params?.project_name) {
        query.set("project_name", params.project_name);
      }
      const suffix = query.toString() ? `?${query.toString()}` : "";
      return fetchJson<OrganizationWorkspaceOperations>(`/admin/organization-workspace/operations${suffix}`);
    },
    getSecretAliases: () =>
      fetchJson<SecretAlias[]>("/admin/secret-aliases"),
    upsertSecretAlias: (payload: {
      alias: string;
      env_var_name: string;
      description?: string | null;
      usage_scope?: string | null;
    }) =>
      fetchJson<SecretAlias>("/admin/secret-aliases", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    deleteSecretAlias: (alias: string) =>
      fetchJson<DeleteSecretAliasResponse>("/admin/secret-aliases/delete", {
        method: "POST",
        body: JSON.stringify({ alias }),
      }),
    upsertOrganizationTeam: (payload: {
      organization_name?: string | null;
      team_name: string;
      description?: string | null;
      manager_usernames: string[];
    }) =>
      fetchJson<OrganizationTeam>("/admin/organization-workspace/teams", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    upsertOrganizationProject: (payload: {
      organization_name?: string | null;
      team_name?: string | null;
      project_name: string;
      description?: string | null;
    }) =>
      fetchJson<OrganizationProject>("/admin/organization-workspace/projects", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    upsertOrganizationMembership: (payload: {
      username: string;
      organization_name?: string | null;
      team_name?: string | null;
      project_name?: string | null;
      role: string;
      note?: string | null;
    }) =>
      fetchJson<OrganizationMembership>("/admin/organization-workspace/memberships", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    removeOrganizationMembership: (
      username: string,
      payload: {
        organization_name?: string | null;
        team_name?: string | null;
        project_name?: string | null;
        reason: string;
      },
    ) =>
      fetchJson<OrganizationRemovalEvent>(
        `/admin/organization-workspace/memberships/${encodeURIComponent(username)}/remove`,
        {
          method: "POST",
          body: JSON.stringify(payload),
        },
      ),
    createOrganizationAssignment: (payload: {
      organization_name?: string | null;
      team_name?: string | null;
      project_name?: string | null;
      work_type: string;
      title: string;
      subject_id?: string | null;
      assigned_to?: string | null;
      details?: Record<string, unknown>;
    }) =>
      fetchJson<OrganizationAssignment>("/admin/organization-workspace/assignments", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    updateOrganizationAssignment: (
      assignmentId: string,
      payload: {
        status?: string | null;
        assigned_to?: string | null;
        title?: string | null;
        details?: Record<string, unknown> | null;
        comment?: string | null;
      },
    ) =>
      fetchJson<OrganizationAssignment>(
        `/admin/organization-workspace/assignments/${encodeURIComponent(assignmentId)}`,
        {
          method: "POST",
          body: JSON.stringify(payload),
        },
      ),
    addOrganizationAssignmentComment: (assignmentId: string, body: string) =>
      fetchJson<OrganizationAssignmentComment>(
        `/admin/organization-workspace/assignments/${encodeURIComponent(assignmentId)}/comments`,
        {
          method: "POST",
          body: JSON.stringify({ body }),
        },
      ),
    getTargetProfileActivity: (profileName: string) =>
      fetchJson<TargetProfileActivity>(
        `/maintenance/live-workload-target-profiles/${encodeURIComponent(profileName)}/activity`,
      ),
    getTargetProfileExplanation: (profileName: string) =>
      fetchJson<TargetProfileExplanation>(
        `/maintenance/live-workload-target-profiles/${encodeURIComponent(profileName)}/explanation`,
      ),
    upsertTargetProfile: (payload: UpsertTargetProfileRequest) =>
      fetchJson<TargetProfile>("/maintenance/live-workload-target-profiles", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    deleteTargetProfile: (profileName: string, reason?: string) =>
      fetchJson<DeleteTargetProfileResponse>(`/maintenance/live-workload-target-profiles/${encodeURIComponent(profileName)}`, {
        method: "DELETE",
        body: JSON.stringify({ reason: reason || "dashboard-target-profile-delete" }),
      }),
    validateTargetProfile: (profileName: string) =>
      fetchJson<RuntimeActionResponse>(`/maintenance/live-workload-target-profiles/${encodeURIComponent(profileName)}/validate`, {
        method: "POST",
        body: JSON.stringify({
          changed_by: config.actorId || "studio",
          reason: "dashboard-target-validation",
        }),
      }),
    runTargetProfileDriftProof: (profileName: string) =>
      fetchJson<RuntimeActionResponse>(`/maintenance/live-workload-target-profiles/${encodeURIComponent(profileName)}/drift-proof`, {
        method: "POST",
        body: JSON.stringify({
          changed_by: config.actorId || "studio",
          reason: "dashboard-target-drift-proof",
          persist: true,
        }),
      }),
    runTargetProfileOperationalValidation: async (profileName: string) =>
      fetchJson<RuntimeActionResponse>(
        `/maintenance/live-workload-target-profiles/${encodeURIComponent(profileName)}/operational-validation`,
        {
          method: "POST",
          body: JSON.stringify({
            changed_by: config.actorId || "studio",
            expected_backend: await resolveExpectedBackend(),
            reason: "dashboard-target-operational-validation",
            process_backups: true,
            cleanup: true,
            run_queue_validation: true,
            run_workload_validation: true,
            run_live_workload_drift_proof: true,
            run_worker_recovery_validation: true,
          }),
        },
      ),
    runTargetProfileCanaryVerify: async (profileName: string) =>
      fetchJson<CanaryVerifierResponse>(
        `/maintenance/live-workload-target-profiles/${encodeURIComponent(profileName)}/canary-verify`,
        {
          method: "POST",
          body: JSON.stringify({
            changed_by: config.actorId || "studio",
            expected_backend: await resolveExpectedBackend(),
            reason: "dashboard-target-canary-verifier",
            process_backups: true,
            cleanup: true,
            run_queue_validation: true,
            run_workload_validation: true,
            run_worker_recovery_validation: true,
            queue_success_jobs: 2,
            queue_failure_jobs: 1,
            queue_delay_seconds: 0,
            run_inline_queue_worker: true,
            workload_rounds: 3,
            workload_maintenance_pause_jobs: 3,
            inject_maintenance_mode_pause: true,
          }),
        },
      ),
    getProofBundles: () =>
      fetchJson<ProofBundleRecord[]>("/maintenance/live-workload-proof-bundles"),
    exportProofBundle: () =>
      fetchJson<ProofBundleExportResponse>("/maintenance/live-workload-proof-bundles/export", {
        method: "POST",
        body: JSON.stringify({
          changed_by: config.actorId || "studio",
          reason: "dashboard-proof-bundle-export",
        }),
      }),
    inspectProofBundle: (path: string) =>
      fetchJson<ProofBundleInspection>("/maintenance/live-workload-proof-bundles/inspect", {
        method: "POST",
        body: JSON.stringify({ path }),
      }),
    deleteProofBundle: (path: string) =>
      fetchJson<ProofBundleDeleteResponse>("/maintenance/live-workload-proof-bundles/delete", {
        method: "POST",
        body: JSON.stringify({
          path,
          reason: "dashboard-proof-bundle-delete",
        }),
      }),
    emitAlerts: () =>
      fetchJson<RuntimeActionResponse>("/maintenance/emit-control-plane-alerts", { method: "POST" }),
    runRuntimeRehearsal: async () =>
      fetchJson<RuntimeActionResponse>("/maintenance/control-plane-runtime-rehearsal", {
        method: "POST",
        body: JSON.stringify({
          changed_by: config.actorId || "studio",
          expected_backend: await resolveExpectedBackend(),
          reason: "dashboard-runtime-rehearsal",
          ignore_deployment_readiness: true,
        }),
      }),
    runOperationalValidation: async () =>
      fetchJson<RuntimeActionResponse>("/maintenance/control-plane-operational-validation", {
        method: "POST",
        body: JSON.stringify({
          changed_by: config.actorId || "studio",
          expected_backend: await resolveExpectedBackend(),
          reason: "dashboard-operational-validation",
          process_backups: true,
          cleanup: true,
          run_queue_validation: true,
          run_workload_validation: true,
          run_live_workload_drift_proof: true,
          run_worker_recovery_validation: true,
        }),
      }),
    acknowledgeAlert: (alertId: string, note: string) =>
      fetchJson<AlertRecord>(`/control-plane-alerts/${alertId}/acknowledge`, {
        method: "POST",
        body: JSON.stringify({ acknowledgement_note: note }),
      }),
  };
}
