import { useEffect, useMemo, useState } from "react";

import CommandLayout from "../components/CommandLayout";
import MetricCard from "../components/MetricCard";
import { useAuth } from "../lib/auth";
import { useBackendApi } from "../lib/api";
import { formatDate, statusTone } from "../lib/format";
import type {
  TargetProfile,
  TargetProfileActivity,
  TargetProfileExplanation,
  UpsertTargetProfileRequest,
} from "../lib/types";
import { useRevealMotion } from "../hooks/useRevealMotion";

type TargetProfileFormState = Omit<
  UpsertTargetProfileRequest,
  "approved_headers" | "drift_headers" | "approved_expected_statuses" | "drift_expected_statuses" | "request_timeout_seconds"
> & {
  approved_headers_text: string;
  drift_headers_text: string;
  approved_expected_statuses_text: string;
  drift_expected_statuses_text: string;
  request_timeout_seconds_text: string;
};

const emptyForm: TargetProfileFormState = {
  name: "",
  approved_target_base_url: "",
  drift_target_base_url: "",
  organization_name: "",
  team_name: "",
  project_name: "",
  environment_name: "",
  approved_probe_url: "",
  drift_probe_url: "",
  approved_action_url: "",
  drift_action_url: "",
  approved_probe_method: "GET",
  drift_probe_method: "GET",
  approved_action_method: "GET",
  drift_action_method: "GET",
  approved_headers_text: "",
  drift_headers_text: "",
  approved_expected_statuses_text: "200",
  drift_expected_statuses_text: "200",
  request_timeout_seconds_text: "",
  enabled: true,
  description: "",
};

function isCustomized(profile: TargetProfile) {
  return Boolean(
    profile.approved_probe_url ||
      profile.drift_probe_url ||
      profile.approved_action_url ||
      profile.drift_action_url ||
      profile.approved_probe_method ||
      profile.drift_probe_method ||
      profile.approved_action_method ||
      profile.drift_action_method ||
      profile.approved_headers ||
      profile.drift_headers ||
      profile.approved_expected_statuses ||
      profile.drift_expected_statuses ||
      profile.request_timeout_seconds,
  );
}

function stringifyHeaders(headers?: Record<string, string> | null) {
  return headers ? JSON.stringify(headers, null, 2) : "";
}

function stringifyStatuses(statuses?: number[] | null) {
  return statuses?.length ? statuses.join(", ") : "";
}

function parseHeaders(text: string) {
  const trimmed = text.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = JSON.parse(trimmed);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Headers must be a JSON object.");
  }
  return Object.fromEntries(
    Object.entries(parsed).map(([key, value]) => [key, String(value)]),
  ) as Record<string, string>;
}

function parseStatuses(text: string) {
  const trimmed = text.trim();
  if (!trimmed) {
    return null;
  }
  const statuses = trimmed
    .split(",")
    .map((value) => Number.parseInt(value.trim(), 10))
    .filter((value) => Number.isFinite(value));
  return statuses.length ? statuses : null;
}

function CountBars({
  title,
  counts,
}: {
  title: string;
  counts: Record<string, number>;
}) {
  const entries = Object.entries(counts).sort((left, right) => right[1] - left[1]);
  const max = entries.length ? Math.max(...entries.map(([, count]) => count)) : 1;

  return (
    <div className="graph-card">
      <div className="graph-card-head">
        <strong>{title}</strong>
        <small>{entries.length ? `${entries.length} categories` : "No activity yet"}</small>
      </div>
      <div className="count-bars">
        {entries.length ? (
          entries.map(([key, count]) => (
            <div className="count-bar-row" key={key}>
              <div className="count-bar-meta">
                <span>{key}</span>
                <strong>{count}</strong>
              </div>
              <div className="count-bar-track">
                <div className="count-bar-fill" style={{ width: `${(count / max) * 100}%` }} />
              </div>
            </div>
          ))
        ) : (
          <div className="graph-empty">No categorized activity yet.</div>
        )}
      </div>
    </div>
  );
}

function LatestRunGraph({
  validation,
  proof,
  canary,
  operational,
}: {
  validation: string;
  proof: string;
  canary: string;
  operational: string;
}) {
  const stages = [
    { label: "Validate", value: validation },
    { label: "Drift proof", value: proof },
    { label: "Canary", value: canary },
    { label: "Operational", value: operational },
  ];

  return (
    <div className="graph-card">
      <div className="graph-card-head">
        <strong>Latest run posture</strong>
        <small>Current state across the target workflow</small>
      </div>
      <div className="run-stage-strip">
        {stages.map((stage) => (
          <div className="run-stage" key={stage.label}>
            <span className={`run-stage-dot tone-${statusTone(stage.value)}`} />
            <div className="cell-stack">
              <small>{stage.label}</small>
              <strong>{stage.value}</strong>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function TargetsPage() {
  const api = useBackendApi();
  const { isAdmin } = useAuth();
  const [configOpen, setConfigOpen] = useState(false);
  const [profiles, setProfiles] = useState<TargetProfile[]>([]);
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState<"all" | "built_in" | "custom">("all");
  const [stateFilter, setStateFilter] = useState<"all" | "enabled" | "disabled">("all");
  const [behaviorFilter, setBehaviorFilter] = useState<"all" | "default" | "customized">("all");
  const [organizationFilter, setOrganizationFilter] = useState<string>("all");
  const [teamFilter, setTeamFilter] = useState<string>("all");
  const [projectFilter, setProjectFilter] = useState<string>("all");
  const [environmentFilter, setEnvironmentFilter] = useState<string>("all");
  const [eventFilter, setEventFilter] = useState<string>("all");
  const [alertFilter, setAlertFilter] = useState<string>("all");
  const [form, setForm] = useState<TargetProfileFormState>(emptyForm);
  const [activity, setActivity] = useState<TargetProfileActivity | null>(null);
  const [explanation, setExplanation] = useState<TargetProfileExplanation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionState, setActionState] = useState<string | null>(null);
  const [actionProgress, setActionProgress] = useState(0);

  useRevealMotion(".targets-page", []);

  const load = async () => {
    setError(null);
    setProfiles(await api.getTargetProfiles());
  };

  useEffect(() => {
    load()
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!selectedName) {
      setActivity(null);
      setExplanation(null);
      return;
    }
    api
      .getTargetProfileActivity(selectedName)
      .then(setActivity)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
    api
      .getTargetProfileExplanation(selectedName)
      .then(setExplanation)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [api, selectedName]);

  useEffect(() => {
    if (!actionState) {
      setActionProgress(0);
      return;
    }
    setActionProgress(12);
    const timer = window.setInterval(() => {
      setActionProgress((current) => {
        if (current >= 88) {
          return current;
        }
        return Math.min(88, current + (current < 40 ? 11 : current < 68 ? 7 : 4));
      });
    }, 320);
    return () => window.clearInterval(timer);
  }, [actionState]);

  const selected = useMemo(
    () => profiles.find((profile) => profile.name === selectedName) ?? null,
    [profiles, selectedName],
  );
  const profileEditingDisabled = Boolean(selected?.built_in) || !isAdmin;

  const customProfiles = useMemo(() => profiles.filter((profile) => !profile.built_in), [profiles]);

  const organizationOptions = useMemo(
    () => Array.from(new Set(profiles.map((profile) => profile.organization_name || "default"))).sort(),
    [profiles],
  );
  const teamOptions = useMemo(
    () => Array.from(new Set(profiles.map((profile) => profile.team_name || "unscoped"))).sort(),
    [profiles],
  );
  const projectOptions = useMemo(
    () => Array.from(new Set(profiles.map((profile) => profile.project_name || "default-project"))).sort(),
    [profiles],
  );
  const environmentOptions = useMemo(
    () => Array.from(new Set(profiles.map((profile) => profile.environment_name || "default"))).sort(),
    [profiles],
  );

  const filteredProfiles = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return profiles.filter((profile) => {
      const sourceMatch =
        sourceFilter === "all" || (sourceFilter === "built_in" ? profile.built_in : !profile.built_in);
      const stateMatch =
        stateFilter === "all" || (stateFilter === "enabled" ? profile.enabled : !profile.enabled);
      const behaviorMatch =
        behaviorFilter === "all" ||
        (behaviorFilter === "customized" ? isCustomized(profile) : !isCustomized(profile));
      const organizationMatch =
        organizationFilter === "all" || (profile.organization_name || "default") === organizationFilter;
      const teamMatch = teamFilter === "all" || (profile.team_name || "unscoped") === teamFilter;
      const projectMatch =
        projectFilter === "all" || (profile.project_name || "default-project") === projectFilter;
      const environmentMatch =
        environmentFilter === "all" || (profile.environment_name || "default") === environmentFilter;
      const queryMatch =
        !normalizedQuery ||
        [
          profile.name,
          profile.description,
          profile.source,
          profile.organization_name,
          profile.team_name,
          profile.project_name,
          profile.environment_name,
          profile.approved_target_base_url,
          profile.drift_target_base_url,
          profile.approved_probe_url,
          profile.drift_probe_url,
          profile.approved_action_url,
          profile.drift_action_url,
          profile.approved_probe_method,
          profile.drift_probe_method,
          profile.approved_action_method,
          profile.drift_action_method,
          stringifyStatuses(profile.approved_expected_statuses),
          stringifyStatuses(profile.drift_expected_statuses),
          profile.request_timeout_seconds,
          profile.approved_headers ? JSON.stringify(profile.approved_headers) : null,
          profile.drift_headers ? JSON.stringify(profile.drift_headers) : null,
        ]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(normalizedQuery));
      return (
        sourceMatch &&
        stateMatch &&
        behaviorMatch &&
        organizationMatch &&
        teamMatch &&
        projectMatch &&
        environmentMatch &&
        queryMatch
      );
    });
  }, [
    behaviorFilter,
    environmentFilter,
    organizationFilter,
    profiles,
    projectFilter,
    query,
    sourceFilter,
    stateFilter,
    teamFilter,
  ]);

  const run = async (label: string, action: () => Promise<unknown>) => {
    setActionState(`${label}...`);
    setActionProgress(12);
    setError(null);
    try {
      await action();
      await load();
      setActionProgress(100);
      setActionState(`${label} done`);
      window.setTimeout(() => {
        setActionState(null);
        setActionProgress(0);
      }, 1800);
    } catch (err) {
      setActionProgress(100);
      setActionState(null);
      setError(err instanceof Error ? err.message : String(err));
      window.setTimeout(() => setActionProgress(0), 250);
    }
  };

  const startCreate = () => {
    setSelectedName(null);
    setForm(emptyForm);
  };

  const startEdit = (profile: TargetProfile) => {
    setSelectedName(profile.name);
    setForm({
      name: profile.name,
      approved_target_base_url: profile.approved_target_base_url,
      drift_target_base_url: profile.drift_target_base_url,
      organization_name: profile.organization_name || "",
      team_name: profile.team_name || "",
      project_name: profile.project_name || "",
      environment_name: profile.environment_name || "",
      approved_probe_url: profile.approved_probe_url || "",
      drift_probe_url: profile.drift_probe_url || "",
      approved_action_url: profile.approved_action_url || "",
      drift_action_url: profile.drift_action_url || "",
      approved_probe_method: profile.approved_probe_method || "GET",
      drift_probe_method: profile.drift_probe_method || "GET",
      approved_action_method: profile.approved_action_method || "GET",
      drift_action_method: profile.drift_action_method || "GET",
      approved_headers_text: stringifyHeaders(profile.approved_headers),
      drift_headers_text: stringifyHeaders(profile.drift_headers),
      approved_expected_statuses_text: stringifyStatuses(profile.approved_expected_statuses) || "200",
      drift_expected_statuses_text: stringifyStatuses(profile.drift_expected_statuses) || "200",
      request_timeout_seconds_text:
        profile.request_timeout_seconds != null ? String(profile.request_timeout_seconds) : "",
      enabled: profile.enabled,
      description: profile.description || "",
    });
  };

  const submit = async () => {
    await run(selected ? "Updating target profile" : "Creating target profile", async () => {
      const approvedHeaders = parseHeaders(form.approved_headers_text);
      const driftHeaders = parseHeaders(form.drift_headers_text);
      const approvedExpectedStatuses = parseStatuses(form.approved_expected_statuses_text);
      const driftExpectedStatuses = parseStatuses(form.drift_expected_statuses_text);
      const requestTimeoutSeconds = form.request_timeout_seconds_text.trim()
        ? Number.parseFloat(form.request_timeout_seconds_text.trim())
        : null;
      await api.upsertTargetProfile({
        ...form,
        organization_name: form.organization_name?.trim() || null,
        team_name: form.team_name?.trim() || null,
        project_name: form.project_name?.trim() || null,
        environment_name: form.environment_name?.trim() || null,
        approved_probe_url: form.approved_probe_url?.trim() || null,
        drift_probe_url: form.drift_probe_url?.trim() || null,
        approved_action_url: form.approved_action_url?.trim() || null,
        drift_action_url: form.drift_action_url?.trim() || null,
        approved_probe_method: form.approved_probe_method?.trim() || null,
        drift_probe_method: form.drift_probe_method?.trim() || null,
        approved_action_method: form.approved_action_method?.trim() || null,
        drift_action_method: form.drift_action_method?.trim() || null,
        approved_headers: approvedHeaders,
        drift_headers: driftHeaders,
        approved_expected_statuses: approvedExpectedStatuses,
        drift_expected_statuses: driftExpectedStatuses,
        request_timeout_seconds: requestTimeoutSeconds,
      });
    });
    startCreate();
  };

  const latestValidationStatus = String(activity?.latest_validation?.status || "n/a");
  const latestProofStatus = activity?.latest_drift_proof
    ? (activity.latest_drift_proof.passed ? "passed" : "failed")
    : "n/a";
  const latestCanaryStatus = String(activity?.latest_canary_verification?.verdict || "n/a");
  const latestOperationalStatus = String(activity?.latest_operational_validation?.status || "n/a");
  const actionWaitingOnBackend = Boolean(actionState) && actionProgress >= 88;
  const actionProgressLabel = actionWaitingOnBackend ? "Waiting on backend" : `${actionProgress}%`;
  const visibleEvents = useMemo(
    () => activity?.recent_events.filter((event) => eventFilter === "all" || event.category === eventFilter) ?? [],
    [activity?.recent_events, eventFilter],
  );
  const visibleAlerts = useMemo(
    () => activity?.recent_alerts.filter((alert) => alertFilter === "all" || alert.category === alertFilter) ?? [],
    [activity?.recent_alerts, alertFilter],
  );

  return (
    <div className="targets-page">
      <CommandLayout
        title="Live workload targets"
        eyebrow="Target registry"
        description="Define where validation comes from, where drift proof writes, and which profiles are safe to run."
        configOpen={configOpen}
        onOpenConfig={() => setConfigOpen(true)}
        onCloseConfig={() => setConfigOpen(false)}
        meta={
          <>
            <span>{actionState || (loading ? "Loading target registry..." : "Manage external proof targets")}</span>
            {error ? <strong className="error-text">{error}</strong> : null}
          </>
        }
      >
        <section className="section-grid">
          <MetricCard label="Profiles" value={profiles.length} caption="Built-in and custom target profiles." />
          <MetricCard label="Custom" value={customProfiles.length} caption="Profiles you control from the UI." />
          <MetricCard
            label="Customized"
            value={profiles.filter((profile) => isCustomized(profile)).length}
            caption="Profiles using explicit validation or proof URLs."
          />
          <MetricCard
            label="Selected"
            value={selected ? selected.name : "none"}
            caption="Current target in focus."
          />
        </section>

        <section className="dashboard-grid">
          <article className="glass-panel wide signal-accent-cyan" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Target profiles</span>
                <h2>Registry, source, and routing behavior</h2>
                <small>Filter by origin, state, or custom override behavior before running proof.</small>
              </div>
              {isAdmin ? (
                <button className="ghost-button small-button" onClick={startCreate} type="button">
                  New profile
                </button>
              ) : null}
            </div>

            <div className="filter-toolbar">
              <label className="filter-field filter-field-wide">
                <span>Search</span>
                <input
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="name, url, description"
                  type="text"
                  value={query}
                />
              </label>
              <label className="filter-field">
                <span>Source</span>
                <select onChange={(event) => setSourceFilter(event.target.value as typeof sourceFilter)} value={sourceFilter}>
                  <option value="all">All</option>
                  <option value="built_in">Built-in</option>
                  <option value="custom">Custom</option>
                </select>
              </label>
              <label className="filter-field">
                <span>State</span>
                <select onChange={(event) => setStateFilter(event.target.value as typeof stateFilter)} value={stateFilter}>
                  <option value="all">All</option>
                  <option value="enabled">Enabled</option>
                  <option value="disabled">Disabled</option>
                </select>
              </label>
              <label className="filter-field">
                <span>Org</span>
                <select onChange={(event) => setOrganizationFilter(event.target.value)} value={organizationFilter}>
                  <option value="all">All</option>
                  {organizationOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label className="filter-field">
                <span>Team</span>
                <select onChange={(event) => setTeamFilter(event.target.value)} value={teamFilter}>
                  <option value="all">All</option>
                  {teamOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label className="filter-field">
                <span>Project</span>
                <select onChange={(event) => setProjectFilter(event.target.value)} value={projectFilter}>
                  <option value="all">All</option>
                  {projectOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label className="filter-field">
                <span>Env</span>
                <select onChange={(event) => setEnvironmentFilter(event.target.value)} value={environmentFilter}>
                  <option value="all">All</option>
                  {environmentOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label className="filter-field">
                <span>Behavior</span>
                <select
                  onChange={(event) => setBehaviorFilter(event.target.value as typeof behaviorFilter)}
                  value={behaviorFilter}
                >
                  <option value="all">All</option>
                  <option value="default">Default routing</option>
                  <option value="customized">Custom URLs</option>
                </select>
              </label>
            </div>

            <div className="table-wrap">
              <table className="signal-table targets-table">
                <colgroup>
                  <col className="col-target-profile" />
                  <col className="col-target-override" />
                  <col className="col-target-route" />
                  <col className="col-target-override" />
                  <col className="col-target-override" />
                  <col className="col-target-override" />
                  <col className="col-tight" />
                </colgroup>
                <thead>
                  <tr>
                    <th>Profile</th>
                    <th>Scope</th>
                    <th>Base routing</th>
                    <th>Validation</th>
                    <th>Proof</th>
                    <th>Auth & timeout</th>
                    <th>State</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredProfiles.map((profile) => (
                    <tr
                      className={`interactive-row ${selectedName === profile.name ? "is-selected" : ""}`}
                      key={profile.name}
                      onClick={() => (profile.built_in || !isAdmin ? setSelectedName(profile.name) : startEdit(profile))}
                    >
                      <td>
                        <div className="cell-stack">
                          <strong>{profile.name}</strong>
                          <small className="source-label">
                            {profile.built_in ? "Built-in" : "Custom"} · {profile.source === "built-in" ? "system" : "file-backed"}
                          </small>
                          <small className="row-description">
                            {profile.description || (profile.built_in ? "Public target profile." : "Custom target profile.")}
                          </small>
                        </div>
                      </td>
                      <td>
                        <div className="cell-stack">
                          <small>Org · {profile.organization_name || "default"}</small>
                          <small>Team · {profile.team_name || "unscoped"}</small>
                          <small>Project · {profile.project_name || "default-project"}</small>
                          <small>Env · {profile.environment_name || "default"}</small>
                        </div>
                      </td>
                      <td>
                        <div className="cell-stack">
                          <span className="table-route-label">Approved</span>
                          <code className="table-url">{profile.approved_target_base_url}</code>
                          <span className="table-route-label">Drift</span>
                          <code className="table-url">{profile.drift_target_base_url}</code>
                        </div>
                      </td>
                      <td>
                        <div className="cell-stack">
                          <span className={`tone-chip tone-${profile.approved_probe_url || profile.drift_probe_url ? "mint" : "neutral"}`}>
                            {profile.approved_probe_url || profile.drift_probe_url ? "custom" : "default"}
                          </span>
                          <small>
                            {(profile.approved_probe_method || "GET")} / {(profile.drift_probe_method || "GET")}
                          </small>
                          <small>
                            {profile.approved_probe_url || profile.drift_probe_url
                              ? "Explicit validation URLs set"
                              : "Uses derived probe routing"}
                          </small>
                        </div>
                      </td>
                      <td>
                        <div className="cell-stack">
                          <span className={`tone-chip tone-${profile.approved_action_url || profile.drift_action_url ? "mint" : "neutral"}`}>
                            {profile.approved_action_url || profile.drift_action_url ? "custom" : "default"}
                          </span>
                          <small>
                            {(profile.approved_action_method || "GET")} / {(profile.drift_action_method || "GET")}
                          </small>
                          <small>
                            {profile.approved_action_url || profile.drift_action_url
                              ? "Explicit proof destinations"
                              : "Uses base or mapped action routing"}
                          </small>
                        </div>
                      </td>
                      <td>
                        <div className="cell-stack">
                          <span className={`tone-chip tone-${profile.approved_headers || profile.drift_headers ? "mint" : "neutral"}`}>
                            {profile.approved_headers || profile.drift_headers ? "headers" : "open"}
                          </span>
                          <small>
                            {profile.request_timeout_seconds != null
                              ? `${profile.request_timeout_seconds}s timeout`
                              : "default timeout"}
                          </small>
                          <small>
                            {profile.approved_expected_statuses?.length || profile.drift_expected_statuses?.length
                              ? `expects ${stringifyStatuses(profile.approved_expected_statuses) || "200"}`
                              : "expects 200"}
                          </small>
                        </div>
                      </td>
                      <td>
                        <div className="cell-stack">
                          <span className={`tone-chip tone-${profile.enabled ? "good" : "warn"}`}>
                            {profile.enabled ? "enabled" : "disabled"}
                          </span>
                          <span className={`tone-chip tone-${statusTone(profile.built_in ? "neutral" : "fresh")}`}>
                            {profile.built_in ? "built-in" : "custom"}
                          </span>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {filteredProfiles.length === 0 ? (
                    <tr>
                      <td className="empty-row" colSpan={7}>
                        No target profiles match the current filters.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </article>

          <article className="glass-panel signal-accent-mint" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">{selected ? "Edit profile" : "Create profile"}</span>
                <h2>{selected ? selected.name : "New external target pair"}</h2>
                <small>
                  {selected
                    ? "Tune where validation and proof run for this profile."
                    : "Base URLs are required. Validation and proof overrides are optional."}
                </small>
              </div>
            </div>
            <div className="targets-form">
              <fieldset className="targets-form-shell" disabled={profileEditingDisabled}>
              <div className="targets-form-section">
                <span className="targets-section-title">Identity</span>
                <p className="targets-section-copy">Default base routing for approved and drift destinations.</p>
              </div>
              <label>
                <span>Name</span>
                <input
                  disabled={Boolean(selected?.built_in)}
                  onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                  value={form.name}
                />
              </label>
              <label>
                <span>Approved target</span>
                <input
                  disabled={Boolean(selected?.built_in)}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, approved_target_base_url: event.target.value }))
                  }
                  value={form.approved_target_base_url}
                />
              </label>
              <label>
                <span>Drift target</span>
                <input
                  disabled={Boolean(selected?.built_in)}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, drift_target_base_url: event.target.value }))
                  }
                  value={form.drift_target_base_url}
                />
              </label>
              <label>
                <span>Organization</span>
                <input
                  disabled={Boolean(selected?.built_in)}
                  onChange={(event) => setForm((current) => ({ ...current, organization_name: event.target.value }))}
                  placeholder="default"
                  value={form.organization_name || ""}
                />
              </label>
              <label>
                <span>Team</span>
                <input
                  disabled={Boolean(selected?.built_in)}
                  onChange={(event) => setForm((current) => ({ ...current, team_name: event.target.value }))}
                  placeholder="platform"
                  value={form.team_name || ""}
                />
              </label>
              <label>
                <span>Project</span>
                <input
                  disabled={Boolean(selected?.built_in)}
                  onChange={(event) => setForm((current) => ({ ...current, project_name: event.target.value }))}
                  placeholder="checkout-reliability"
                  value={form.project_name || ""}
                />
              </label>
              <label>
                <span>Environment</span>
                <input
                  disabled={Boolean(selected?.built_in)}
                  onChange={(event) => setForm((current) => ({ ...current, environment_name: event.target.value }))}
                  placeholder="prod"
                  value={form.environment_name || ""}
                />
              </label>
              <label>
                <span>Description</span>
                <input
                  disabled={Boolean(selected?.built_in)}
                  onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                  value={form.description || ""}
                />
              </label>

              <div className="targets-form-section">
                <span className="targets-section-title">Validation overrides</span>
                <p className="targets-section-copy">Used by Validate instead of derived probe paths. Real targets usually use GET on /health or /ready.</p>
              </div>
              <label>
                <span>Approved validation URL</span>
                <input
                  disabled={Boolean(selected?.built_in)}
                  onChange={(event) => setForm((current) => ({ ...current, approved_probe_url: event.target.value }))}
                  placeholder="https://api.example.com/health"
                  value={form.approved_probe_url || ""}
                />
              </label>
              <label>
                <span>Approved validation method</span>
                <select
                  disabled={Boolean(selected?.built_in)}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, approved_probe_method: event.target.value }))
                  }
                  value={form.approved_probe_method || "GET"}
                >
                  <option value="GET">GET</option>
                  <option value="POST">POST</option>
                  <option value="HEAD">HEAD</option>
                  <option value="PUT">PUT</option>
                  <option value="PATCH">PATCH</option>
                  <option value="DELETE">DELETE</option>
                </select>
              </label>
              <label>
                <span>Drift validation URL</span>
                <input
                  disabled={Boolean(selected?.built_in)}
                  onChange={(event) => setForm((current) => ({ ...current, drift_probe_url: event.target.value }))}
                  placeholder="https://dev-api.example.com/health"
                  value={form.drift_probe_url || ""}
                />
              </label>
              <label>
                <span>Drift validation method</span>
                <select
                  disabled={Boolean(selected?.built_in)}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, drift_probe_method: event.target.value }))
                  }
                  value={form.drift_probe_method || "GET"}
                >
                  <option value="GET">GET</option>
                  <option value="POST">POST</option>
                  <option value="HEAD">HEAD</option>
                  <option value="PUT">PUT</option>
                  <option value="PATCH">PATCH</option>
                  <option value="DELETE">DELETE</option>
                </select>
              </label>
              <label>
                <span>Approved expected statuses</span>
                <input
                  disabled={Boolean(selected?.built_in)}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, approved_expected_statuses_text: event.target.value }))
                  }
                  placeholder="200, 204"
                  value={form.approved_expected_statuses_text}
                />
              </label>
              <label>
                <span>Drift expected statuses</span>
                <input
                  disabled={Boolean(selected?.built_in)}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, drift_expected_statuses_text: event.target.value }))
                  }
                  placeholder="200, 204"
                  value={form.drift_expected_statuses_text}
                />
              </label>

              <div className="targets-form-section">
                <span className="targets-section-title">Proof overrides</span>
                <p className="targets-section-copy">Used by Drift proof and Operational validation. Real targets can use GET here too if they only expose safe read endpoints.</p>
              </div>
              <label>
                <span>Approved proof URL</span>
                <input
                  disabled={Boolean(selected?.built_in)}
                  onChange={(event) => setForm((current) => ({ ...current, approved_action_url: event.target.value }))}
                  placeholder="https://api.example.com/anything"
                  value={form.approved_action_url || ""}
                />
              </label>
              <label>
                <span>Approved proof method</span>
                <select
                  disabled={Boolean(selected?.built_in)}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, approved_action_method: event.target.value }))
                  }
                  value={form.approved_action_method || "GET"}
                >
                  <option value="GET">GET</option>
                  <option value="POST">POST</option>
                  <option value="HEAD">HEAD</option>
                  <option value="PUT">PUT</option>
                  <option value="PATCH">PATCH</option>
                  <option value="DELETE">DELETE</option>
                </select>
              </label>
              <label>
                <span>Drift proof URL</span>
                <input
                  disabled={Boolean(selected?.built_in)}
                  onChange={(event) => setForm((current) => ({ ...current, drift_action_url: event.target.value }))}
                  placeholder="https://dev-api.example.com/anything"
                  value={form.drift_action_url || ""}
                />
              </label>
              <label>
                <span>Drift proof method</span>
                <select
                  disabled={Boolean(selected?.built_in)}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, drift_action_method: event.target.value }))
                  }
                  value={form.drift_action_method || "GET"}
                >
                  <option value="GET">GET</option>
                  <option value="POST">POST</option>
                  <option value="HEAD">HEAD</option>
                  <option value="PUT">PUT</option>
                  <option value="PATCH">PATCH</option>
                  <option value="DELETE">DELETE</option>
                </select>
              </label>

              <div className="targets-form-section">
                <span className="targets-section-title">Auth and request policy</span>
                <p className="targets-section-copy">Use JSON headers. Values can reference environment variables with <code>env:NAME</code> or admin-managed aliases with <code>secret:alias</code>.</p>
              </div>
              <label className="wide-field">
                <span>Approved headers JSON</span>
                <textarea
                  disabled={Boolean(selected?.built_in)}
                  onChange={(event) => setForm((current) => ({ ...current, approved_headers_text: event.target.value }))}
                  placeholder={'{\n  "Authorization": "Bearer env:APPROVED_TOKEN"\n}'}
                  rows={5}
                  value={form.approved_headers_text}
                />
              </label>
              <label className="wide-field">
                <span>Drift headers JSON</span>
                <textarea
                  disabled={Boolean(selected?.built_in)}
                  onChange={(event) => setForm((current) => ({ ...current, drift_headers_text: event.target.value }))}
                  placeholder={'{\n  "X-API-Key": "env:DRIFT_API_KEY"\n}'}
                  rows={5}
                  value={form.drift_headers_text}
                />
              </label>
              <label>
                <span>Request timeout seconds</span>
                <input
                  disabled={Boolean(selected?.built_in)}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, request_timeout_seconds_text: event.target.value }))
                  }
                  placeholder="10"
                  value={form.request_timeout_seconds_text}
                />
              </label>

              <label className="checkbox-row">
                <input
                  checked={form.enabled}
                  disabled={Boolean(selected?.built_in)}
                  onChange={(event) => setForm((current) => ({ ...current, enabled: event.target.checked }))}
                  type="checkbox"
                />
                <span>Enabled</span>
              </label>
              <div className="hero-actions">
                <button
                  className="primary-button"
                  disabled={Boolean(selected?.built_in)}
                  onClick={submit}
                  type="button"
                >
                  {selected ? "Save profile" : "Create profile"}
                </button>
                {selected && !selected.built_in && isAdmin ? (
                  <button
                    className="ghost-button"
                    onClick={() =>
                      run("Delete target profile", async () => {
                        await api.deleteTargetProfile(selected.name);
                        startCreate();
                      })
                    }
                    type="button"
                  >
                    Delete
                  </button>
                ) : null}
              </div>
              </fieldset>
              {!isAdmin ? (
                <p className="sheet-note">
                  This session can run target proof, but only admins can create, edit, or delete target profiles.
                </p>
              ) : null}
            </div>
          </article>

          <article className="glass-panel signal-accent-gold" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Actions</span>
                <h2>Run proof against selected target</h2>
                <small>{selected ? `Current profile: ${selected.name}` : "Pick a profile from the registry first."}</small>
              </div>
            </div>
            <div className="drawer-stack">
              <p className="panel-copy">
                Validate checks reachability. Drift proof exercises the noisy service. Canary verify chains validation, drift proof, and operational validation into one promotion verdict.
              </p>
              {actionState ? (
                <div className="action-progress-shell" aria-live="polite">
                  <div className="action-progress-meta">
                    <strong>{actionState}</strong>
                    <span>{actionProgressLabel}</span>
                  </div>
                  <div className="action-progress-track">
                    <div
                      className={`action-progress-fill${actionWaitingOnBackend ? " is-indeterminate" : ""}`}
                      style={{ width: `${actionProgress}%` }}
                    />
                  </div>
                </div>
              ) : null}
              <div className="hero-actions">
                <button
                  className="ghost-button"
                  disabled={!selectedName || Boolean(actionState)}
                  onClick={() => run("Validating target", () => api.validateTargetProfile(selectedName!))}
                  type="button"
                >
                  Validate
                </button>
                <button
                  className="ghost-button"
                  disabled={!selectedName || Boolean(actionState)}
                  onClick={() => run("Running drift proof", () => api.runTargetProfileDriftProof(selectedName!))}
                  type="button"
                >
                  Drift proof
                </button>
                <button
                  className="ghost-button"
                  disabled={!selectedName || Boolean(actionState)}
                  onClick={() => run("Running canary verifier", () => api.runTargetProfileCanaryVerify(selectedName!))}
                  type="button"
                >
                  Canary verify
                </button>
                <button
                  className="primary-button"
                  disabled={!selectedName || Boolean(actionState)}
                  onClick={() =>
                    run("Running operational validation", () => api.runTargetProfileOperationalValidation(selectedName!))
                  }
                  type="button"
                >
                  Operational validation
                </button>
              </div>
              <ul className="signal-list">
                <li>Base URLs define the pair identity and default routing.</li>
                <li>Validation URLs only affect connectivity checks.</li>
                <li>Proof URLs only affect drift proof and operational validation writes.</li>
                <li>Canary verify gives one verdict before promotion instead of making you compare three runs by hand.</li>
                <li>Built-in profiles are read-only but fully runnable.</li>
              </ul>
            </div>
          </article>

          <article className="glass-panel wide signal-accent-violet" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Target intel</span>
                <h2>{selected ? `${selected.name} activity` : "Select a target profile"}</h2>
                <small>
                  {selected
                    ? "Latest validation, proof, operational runs, and related events."
                    : "Click a target row to inspect its history."}
                </small>
              </div>
            </div>
            {selected ? (
              <>
                <section className="section-grid compact-section-grid">
                  <MetricCard label="Validate" value={latestValidationStatus} caption="Latest validation status." />
                  <MetricCard label="Drift proof" value={latestProofStatus} caption="Latest drift-proof result." />
                  <MetricCard label="Canary" value={latestCanaryStatus} caption="Latest promotion verdict." />
                  <MetricCard
                    label="Operational"
                    value={latestOperationalStatus}
                    caption="Latest operational validation result."
                  />
                  <MetricCard label="Incidents" value={activity?.recent_alerts.length ?? 0} caption="Recent alerts tied to this target." />
                </section>
                <section className="detail-grid target-graph-grid">
                  <LatestRunGraph
                    canary={latestCanaryStatus}
                    operational={latestOperationalStatus}
                    proof={latestProofStatus}
                    validation={latestValidationStatus}
                  />
                  <CountBars title="Event categories" counts={activity?.event_category_counts ?? {}} />
                  <CountBars title="Incident categories" counts={activity?.alert_category_counts ?? {}} />
                </section>
                <section className="glass-panel subtle-panel">
                  <div className="panel-header">
                    <div>
                      <span className="eyebrow">Target scope</span>
                      <h2>Who owns this target and where it belongs</h2>
                    </div>
                  </div>
                  <div className="target-tree">
                    <div className="target-tree-group">
                      <span className="target-tree-label">Organization</span>
                      <strong>{selected.organization_name || activity?.organization_name || "default"}</strong>
                    </div>
                    <div className="target-tree-group">
                      <span className="target-tree-label">Team</span>
                      <strong>{selected.team_name || activity?.team_name || "unscoped"}</strong>
                    </div>
                    <div className="target-tree-group">
                      <span className="target-tree-label">Project</span>
                      <strong>{selected.project_name || activity?.project_name || "default-project"}</strong>
                    </div>
                    <div className="target-tree-group">
                      <span className="target-tree-label">Environment</span>
                      <strong>{selected.environment_name || activity?.environment_name || "default"}</strong>
                    </div>
                  </div>
                </section>
                <section className="glass-panel subtle-panel ai-explanation-panel">
                  <div className="panel-header">
                    <div>
                      <span className="eyebrow">AI explanation</span>
                      <h2>{explanation?.title || "Target explanation"}</h2>
                      <small>
                        {explanation
                          ? `${explanation.remediation_provider}${explanation.remediation_model ? ` · ${explanation.remediation_model}` : ""}`
                          : "Waiting for target explanation."}
                      </small>
                    </div>
                    {explanation ? (
                      <span className={`tone-chip tone-${statusTone(explanation.risk)}`}>{explanation.risk}</span>
                    ) : null}
                  </div>
                  {explanation ? (
                    <div className="ai-explanation-grid">
                      <div className="ai-explanation-copy">
                        <p className="panel-copy">{explanation.summary}</p>
                        <div className="detail-grid compact-ai-grid">
                          <div>
                            <span>Immediate action</span>
                            <strong>{explanation.immediate_action}</strong>
                          </div>
                          <div>
                            <span>Long-term fix</span>
                            <strong>{explanation.long_term_fix}</strong>
                          </div>
                        </div>
                      </div>
                      <div className="glass-panel subtle-panel">
                        <div className="panel-header">
                          <div>
                            <span className="eyebrow">Why it said this</span>
                            <h2>Supporting facts</h2>
                          </div>
                        </div>
                        <ul className="signal-list compact">
                          {explanation.supporting_facts.map((fact, index) => (
                            <li key={`${fact}-${index}`}>
                              <p>{fact}</p>
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  ) : (
                    <p className="panel-copy">No explanation available for this target yet.</p>
                  )}
                </section>
                <section className="glass-panel subtle-panel">
                  <div className="panel-header">
                    <div>
                      <span className="eyebrow">Target config tree</span>
                      <h2>Request map</h2>
                      <small>Fast way to understand how this profile is wired.</small>
                    </div>
                  </div>
                  <div className="target-tree">
                    <div className="target-tree-group">
                      <strong>approved</strong>
                      <div className="target-tree-item">
                        <span>base</span>
                        <code>{selected.approved_target_base_url}</code>
                      </div>
                      <div className="target-tree-item">
                        <span>validate</span>
                        <code>{selected.approved_probe_method || "GET"} {selected.approved_probe_url || "(derived)"}</code>
                      </div>
                      <div className="target-tree-item">
                        <span>proof</span>
                        <code>{selected.approved_action_method || "GET"} {selected.approved_action_url || "(base or mapped)"}</code>
                      </div>
                      <div className="target-tree-item">
                        <span>statuses</span>
                        <code>{stringifyStatuses(selected.approved_expected_statuses) || "200"}</code>
                      </div>
                      <div className="target-tree-item">
                        <span>headers</span>
                        <code>{selected.approved_headers ? Object.keys(selected.approved_headers).join(", ") : "none"}</code>
                      </div>
                    </div>
                    <div className="target-tree-group">
                      <strong>drift</strong>
                      <div className="target-tree-item">
                        <span>base</span>
                        <code>{selected.drift_target_base_url}</code>
                      </div>
                      <div className="target-tree-item">
                        <span>validate</span>
                        <code>{selected.drift_probe_method || "GET"} {selected.drift_probe_url || "(derived)"}</code>
                      </div>
                      <div className="target-tree-item">
                        <span>proof</span>
                        <code>{selected.drift_action_method || "GET"} {selected.drift_action_url || "(base or mapped)"}</code>
                      </div>
                      <div className="target-tree-item">
                        <span>statuses</span>
                        <code>{stringifyStatuses(selected.drift_expected_statuses) || "200"}</code>
                      </div>
                      <div className="target-tree-item">
                        <span>headers</span>
                        <code>{selected.drift_headers ? Object.keys(selected.drift_headers).join(", ") : "none"}</code>
                      </div>
                    </div>
                    <div className="target-tree-group">
                      <strong>policy</strong>
                      <div className="target-tree-item">
                        <span>timeout</span>
                        <code>{selected.request_timeout_seconds != null ? `${selected.request_timeout_seconds}s` : "default"}</code>
                      </div>
                      <div className="target-tree-item">
                        <span>source</span>
                        <code>{selected.source}</code>
                      </div>
                      <div className="target-tree-item">
                        <span>mode</span>
                        <code>{selected.built_in ? "built-in" : "custom"} / {selected.enabled ? "enabled" : "disabled"}</code>
                      </div>
                    </div>
                  </div>
                </section>
                <div className="dashboard-grid detail-grid">
                  <div className="glass-panel subtle-panel">
                    <div className="panel-header">
                      <div>
                        <span className="eyebrow">Recent events</span>
                        <h2>Execution trail</h2>
                        <small>
                          {Object.entries(activity?.event_category_counts ?? {})
                            .map(([key, count]) => `${key} ${count}`)
                            .join(" · ") || "No categorized activity yet."}
                        </small>
                      </div>
                    </div>
                    <div className="filter-toolbar">
                      <label className="filter-field">
                        <span>Event type</span>
                        <select onChange={(event) => setEventFilter(event.target.value)} value={eventFilter}>
                          <option value="all">All</option>
                          {Object.keys(activity?.event_category_counts ?? {}).map((key) => (
                            <option key={key} value={key}>
                              {key}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <div className="table-wrap">
                      <table className="signal-table">
                        <thead>
                          <tr>
                            <th>Event</th>
                            <th>Source</th>
                            <th>Status</th>
                            <th>When</th>
                            <th>By</th>
                          </tr>
                        </thead>
                        <tbody>
                          {visibleEvents.map((event) => (
                            <tr key={event.event_id}>
                              <td>
                                <div className="cell-stack">
                                  <strong>{event.summary || event.event_type}</strong>
                                  <small>{event.reason || event.event_type}</small>
                                </div>
                              </td>
                              <td>
                                <span className={`tone-chip tone-${statusTone(event.category)}`}>{event.category}</span>
                              </td>
                              <td>
                                <span className={`tone-chip tone-${statusTone(event.status)}`}>{event.status || "n/a"}</span>
                              </td>
                              <td>{formatDate(event.recorded_at)}</td>
                              <td>{event.changed_by}</td>
                            </tr>
                          ))}
                          {!visibleEvents.length ? (
                            <tr>
                              <td className="empty-row" colSpan={5}>
                                No recent events for this target.
                              </td>
                            </tr>
                          ) : null}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div className="glass-panel subtle-panel">
                    <div className="panel-header">
                      <div>
                        <span className="eyebrow">Related incidents</span>
                        <h2>Alerts touching this target</h2>
                        <small>
                          {Object.entries(activity?.alert_category_counts ?? {})
                            .map(([key, count]) => `${key} ${count}`)
                            .join(" · ") || "No alert categories yet."}
                        </small>
                      </div>
                    </div>
                    <div className="filter-toolbar">
                      <label className="filter-field">
                        <span>Incident type</span>
                        <select onChange={(event) => setAlertFilter(event.target.value)} value={alertFilter}>
                          <option value="all">All</option>
                          {Object.keys(activity?.alert_category_counts ?? {}).map((key) => (
                            <option key={key} value={key}>
                              {key}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <div className="table-wrap">
                      <table className="signal-table">
                        <thead>
                          <tr>
                            <th>Summary</th>
                            <th>Source</th>
                            <th>Severity</th>
                            <th>Status</th>
                            <th>When</th>
                          </tr>
                        </thead>
                        <tbody>
                          {visibleAlerts.map((alert) => (
                            <tr key={alert.alert_id}>
                              <td>
                                <div className="cell-stack">
                                  <strong>{alert.summary}</strong>
                                  <small>{alert.alert_key}</small>
                                </div>
                              </td>
                              <td>
                                <span className={`tone-chip tone-${statusTone(alert.category)}`}>{alert.category}</span>
                              </td>
                              <td>
                                <span className={`tone-chip tone-${statusTone(alert.severity)}`}>{alert.severity}</span>
                              </td>
                              <td>
                                <span className={`tone-chip tone-${statusTone(alert.status)}`}>{alert.status}</span>
                              </td>
                              <td>{formatDate(alert.created_at)}</td>
                            </tr>
                          ))}
                          {!visibleAlerts.length ? (
                            <tr>
                              <td className="empty-row" colSpan={5}>
                                No related alerts recorded for this target.
                              </td>
                            </tr>
                          ) : null}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <p className="panel-copy">Pick a target from the registry to inspect its incidents, validations, and proof history.</p>
            )}
          </article>
        </section>
      </CommandLayout>
    </div>
  );
}
