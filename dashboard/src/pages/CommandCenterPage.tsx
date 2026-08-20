import { useCallback, useEffect, useMemo, useState } from "react";
import { animate } from "animejs";
import { Link } from "react-router-dom";

import ApiConfigSheet from "../components/ApiConfigSheet";
import MetricCard from "../components/MetricCard";
import NavBar from "../components/NavBar";
import ScrollMotionLayer from "../components/ScrollMotionLayer";
import StatusPill from "../components/StatusPill";
import LiveStatusBadge from "../components/LiveStatusBadge";
import { useAuth } from "../lib/auth";
import { useScrollDriftMotion } from "../hooks/useScrollDriftMotion";
import { useBackendApi } from "../lib/api";
import { formatCount, formatDate, formatRelativeHours, statusTone, titleCase } from "../lib/format";
import type {
  AlertRecord,
  AnalyticsResponse,
  HealthResponse,
  IncidentNarrativeResponse,
  OwnerTeamQueue,
  ReadinessResponse,
  RuntimeReviewQueue,
  TrustScoreResponse,
} from "../lib/types";
import { useRevealMotion } from "../hooks/useRevealMotion";

type SnapshotState = {
  health: HealthResponse | null;
  readiness: ReadinessResponse | null;
  analytics: AnalyticsResponse | null;
  trust: TrustScoreResponse | null;
  narrative: IncidentNarrativeResponse | null;
  reviews: RuntimeReviewQueue | null;
  ownerQueue: OwnerTeamQueue | null;
  alerts: AlertRecord[];
};

const initialState: SnapshotState = {
  health: null,
  readiness: null,
  analytics: null,
  trust: null,
  narrative: null,
  reviews: null,
  ownerQueue: null,
  alerts: [],
};

export default function CommandCenterPage() {
  const api = useBackendApi();
  const { isAdmin } = useAuth();
  const [configOpen, setConfigOpen] = useState(false);
  const [snapshot, setSnapshot] = useState<SnapshotState>(initialState);
  const [loading, setLoading] = useState(true);
  const [actionState, setActionState] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useRevealMotion(".command-page", []);
  useScrollDriftMotion("command");

  const load = useCallback(async () => {
    setError(null);
    const [health, readiness, analytics, trust, narrative, reviews, ownerQueue, alerts] = await Promise.all([
      api.getHealth(),
      api.getReadiness(),
      api.getAnalytics(14),
      api.getTrustScore(),
      api.getIncidentNarrative(),
      api.getRuntimeReviewQueue(),
      api.getOwnerTeamQueue(),
      api.getAlerts(10),
    ]);
    setSnapshot({ health, readiness, analytics, trust, narrative, reviews, ownerQueue, alerts });
  }, [api]);

  useEffect(() => {
    load()
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, [load]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.hidden) {
        return;
      }
      load().catch(() => undefined);
    }, 15000);
    return () => window.clearInterval(timer);
  }, [load]);

  useEffect(() => {
    animate(".command-page .hero-grid", {
      opacity: [0, 1],
      translateY: [18, 0],
      duration: 900,
      ease: "outExpo",
    });
  }, []);

  const runAction = useCallback(
    async (label: string, action: () => Promise<unknown>) => {
      setActionState(`${label}...`);
      setError(null);
      try {
        await action();
        await load();
        setActionState(`${label} done`);
        window.setTimeout(() => setActionState(null), 2200);
      } catch (err) {
        setActionState(null);
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [load],
  );

  const findings = snapshot.analytics?.evaluation.findings ?? [];
  const trust = snapshot.trust;
  const narrative = snapshot.narrative;
  const readiness = snapshot.readiness;
  const reviewRows = snapshot.reviews?.reviews.slice(0, 5) ?? [];
  const ownerRows = snapshot.ownerQueue?.requests.slice(0, 5) ?? [];
  const alertRows = snapshot.alerts.slice(0, 6);

  const headlinePills = useMemo(
    () => [
      { label: "Readiness", value: readiness?.ready ? "ready" : snapshot.health?.status || "unknown" },
      { label: "Runtime cadence", value: readiness?.runtime_validation.cadence_status || "unknown" },
      {
        label: "Target cadence",
        value: readiness?.live_workload_target_validation.cadence_status || "unknown",
      },
      { label: "Proof", value: readiness?.live_workload_proof_validation.status || "unknown" },
    ],
    [readiness, snapshot.health?.status],
  );

  return (
    <div className="app-shell command-page">
      <div className="ambient-background command" />
      <ScrollMotionLayer tone="command" />
      <NavBar onOpenConfig={() => setConfigOpen(true)} />
      <main>
        <section className="hero-grid compact">
          <div className="hero-copy">
            <span className="eyebrow">Command center</span>
            <h1>One surface for release proof, governance debt, and live operator actions.</h1>
            <p>
              FastAPI stays the backend authority. This frontend reads health, readiness, analytics,
              queues, and alerts directly, then gives operators direct launch points for rehearsal
              and validation.
            </p>
            <div className="hero-actions">
              {isAdmin ? (
                <>
                  <button
                    className="primary-button"
                    onClick={() => runAction("Runtime rehearsal", () => api.runRuntimeRehearsal())}
                    type="button"
                  >
                    Run Runtime Rehearsal
                  </button>
                  <button
                    className="ghost-button"
                    onClick={() => runAction("Operational validation", () => api.runOperationalValidation())}
                    type="button"
                  >
                    Run Operational Validation
                  </button>
                  <button
                    className="ghost-button"
                    onClick={() => runAction("Emit alerts", () => api.emitAlerts())}
                    type="button"
                  >
                    Emit Alerts
                  </button>
                </>
              ) : null}
            </div>
            <div className="hero-status-row" data-stagger-group>
              {headlinePills.map((item) => (
                <StatusPill key={item.label} label={item.label} value={item.value} />
              ))}
            </div>
            <div className="command-meta">
              <LiveStatusBadge
                actionState={actionState}
                idleLabel="Live polling every 15s"
                loading={loading}
              />
              {error ? <strong className="error-text">{error}</strong> : null}
            </div>
          </div>
          <div className="hero-side-panel">
            <div className="hero-panel-title">
              <span className="eyebrow">Backend pulse</span>
              <strong>{snapshot.health?.database_backend || "unknown"} runtime</strong>
            </div>
            <div className="hero-panel-grid">
              <MetricCard
                label="Blocked teams"
                value={readiness?.blocked_owner_team_count ?? 0}
                caption="Owner teams with deployment debt."
                tone={(readiness?.blocked_owner_team_count ?? 0) > 0 ? "warn" : "good"}
              />
              <MetricCard
                label="Queued jobs"
                value={snapshot.health?.queued_jobs ?? 0}
                caption="Queue pressure right now."
                tone={(snapshot.health?.queued_jobs ?? 0) > 0 ? "warn" : "neutral"}
              />
              <MetricCard
                label="Active workers"
                value={snapshot.health?.active_workers ?? 0}
                caption="Workers heartbeating now."
                tone="good"
              />
              <MetricCard
                label="Trust score"
                value={trust?.score ?? 0}
                caption={trust ? `${trust.grade} · ${trust.status}` : "Confidence across proof, backup, soak, and readiness."}
                tone={statusTone(trust?.status)}
              />
            </div>
          </div>
        </section>

        <section className="horizontal-band metrics-band">
          <MetricCard
            label="Review backlog"
            value={snapshot.reviews?.total_reviews ?? 0}
            caption="Active runtime validation reviews."
            tone={(snapshot.reviews?.stale_reviews ?? 0) > 0 ? "warn" : "neutral"}
          />
          <MetricCard
            label="Owner queue"
            value={snapshot.ownerQueue?.total_requests ?? 0}
            caption="Deployment readiness change-control queue."
            tone={(snapshot.ownerQueue?.rejected_count ?? 0) > 0 ? "bad" : "neutral"}
          />
          <MetricCard
            label="Findings"
            value={findings.length}
            caption="Current analytics findings."
            tone={findings.length > 0 ? "warn" : "good"}
          />
          <MetricCard
            label="Alert stream"
            value={snapshot.alerts.length}
            caption="Latest control-plane incidents."
            tone={snapshot.alerts.length > 0 ? "warn" : "good"}
          />
          <MetricCard
            label="Soak"
            value={snapshot.health?.soak_validation_status || "unknown"}
            caption="Endurance evidence posture."
            tone={statusTone(snapshot.health?.soak_validation_status)}
          />
        </section>

        <section className="dashboard-grid">
          <article className="glass-panel" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Trust score</span>
                <h2>{trust ? `${trust.score} · ${trust.grade}` : "Loading confidence"}</h2>
              </div>
              <StatusPill label="Status" value={trust?.status || "unknown"} />
            </div>
            <div className="mini-metrics">
              <div>
                <span>Degraded factors</span>
                <strong>{trust?.factors.filter((factor) => factor.impact > 0).length ?? 0}</strong>
              </div>
              <div>
                <span>Stable factors</span>
                <strong>{trust?.factors.filter((factor) => factor.status === "passed").length ?? 0}</strong>
              </div>
              <div>
                <span>Running checks</span>
                <strong>{trust?.factors.filter((factor) => factor.status === "running").length ?? 0}</strong>
              </div>
            </div>
            <ul className="signal-list compact">
              {(trust?.factors.length ? trust.factors : []).slice(0, 6).map((factor) => (
                <li key={factor.code}>
                  <span className={`tone-chip tone-${statusTone(factor.status)}`}>{factor.status}</span>
                  <div>
                    <strong>{factor.label}</strong>
                    <p>{factor.summary}</p>
                  </div>
                </li>
              ))}
            </ul>
          </article>

          <article className="glass-panel wide" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Incident narrative</span>
                <h2>{narrative?.headline || "Recent control-plane story"}</h2>
              </div>
              <StatusPill label="State" value={narrative?.status || "unknown"} />
            </div>
            <p className="panel-copy">{narrative?.summary || "Loading recent timeline and likely causes."}</p>
            <div className="issue-columns">
              <div>
                <h3>Likely causes</h3>
                <ul className="signal-list compact">
                  {(narrative?.likely_causes.length ? narrative.likely_causes : ["No active causes surfaced."]).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h3>Immediate actions</h3>
                <ul className="signal-list compact">
                  {(narrative?.immediate_actions.length ? narrative.immediate_actions : ["No action required right now."]).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="table-wrap">
              <table className="signal-table">
                <colgroup>
                  <col className="col-tight" />
                  <col className="col-summary-wide" />
                  <col className="col-tight" />
                  <col className="col-tight" />
                </colgroup>
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Event</th>
                    <th>Type</th>
                    <th>Severity</th>
                  </tr>
                </thead>
                <tbody>
                  {(narrative?.timeline ?? []).slice(0, 6).map((entry) => (
                    <tr key={`${entry.source_type}-${entry.source_id}`}>
                      <td>{formatDate(entry.recorded_at)}</td>
                      <td>
                        <div className="cell-stack">
                          <strong>{entry.title}</strong>
                          <small>{entry.summary}</small>
                        </div>
                      </td>
                      <td>{titleCase(entry.source_type)}</td>
                      <td>
                        <span className={`tone-chip tone-${statusTone(entry.severity || "neutral")}`}>
                          {entry.severity || "n/a"}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {!narrative?.timeline.length ? (
                    <tr>
                      <td className="empty-row" colSpan={4}>
                        No recent narrative timeline yet.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </article>
        </section>

        <section className="horizontal-band quick-links-band" data-reveal>
          <Link className="quick-link-card" to="/command/reviews">
            <span className="eyebrow">Queue</span>
            <strong>Runtime reviews</strong>
            <p>Open the full review backlog, owner rollups, and due-state details.</p>
          </Link>
          <Link className="quick-link-card" to="/command/deployment-debt">
            <span className="eyebrow">Governance</span>
            <strong>Deployment debt</strong>
            <p>See exactly which change-control requests are blocking release readiness.</p>
          </Link>
          <Link className="quick-link-card" to="/command/incidents">
            <span className="eyebrow">Signal</span>
            <strong>Incidents and proof</strong>
            <p>Inspect alerts beside the proof surfaces driving operator pressure.</p>
          </Link>
        </section>

        <section className="glass-panel wide" data-reveal>
          <div className="panel-header">
            <div>
              <span className="eyebrow">System map</span>
              <h2>How the product is organized</h2>
              <small>Tree view for operators who need a fast mental model before they drill into queues and proofs.</small>
            </div>
          </div>
          <div className="target-tree command-tree">
            <div className="target-tree-group">
              <strong>command</strong>
              <div className="target-tree-item">
                <span>trust</span>
                <code>{trust ? `${trust.score} / ${trust.grade} / ${trust.status}` : "loading"}</code>
              </div>
              <div className="target-tree-item">
                <span>readiness</span>
                <code>{readiness?.ready ? "ready" : "blocked"}</code>
              </div>
              <div className="target-tree-item">
                <span>narrative</span>
                <code>{narrative?.status || "unknown"}</code>
              </div>
            </div>
            <div className="target-tree-group">
              <strong>proofs</strong>
              <div className="target-tree-item">
                <span>runtime</span>
                <code>{readiness?.runtime_validation.status || "unknown"} / {readiness?.runtime_validation.cadence_status || "unknown"}</code>
              </div>
              <div className="target-tree-item">
                <span>target</span>
                <code>{readiness?.live_workload_target_validation.status || "unknown"} / {readiness?.live_workload_target_validation.cadence_status || "unknown"}</code>
              </div>
              <div className="target-tree-item">
                <span>workload</span>
                <code>{readiness?.live_workload_proof_validation.status || "unknown"}</code>
              </div>
              <div className="target-tree-item">
                <span>soak</span>
                <code>{snapshot.health?.soak_validation_status || "unknown"}</code>
              </div>
            </div>
            <div className="target-tree-group">
              <strong>governance</strong>
              <div className="target-tree-item">
                <span>reviews</span>
                <code>{formatCount(snapshot.reviews?.total_reviews)} open</code>
              </div>
              <div className="target-tree-item">
                <span>owner debt</span>
                <code>{formatCount(snapshot.ownerQueue?.total_requests)} requests</code>
              </div>
              <div className="target-tree-item">
                <span>alerts</span>
                <code>{formatCount(snapshot.alerts.length)} recent</code>
              </div>
            </div>
          </div>
        </section>

        <section className="dashboard-grid">
          <article className="glass-panel wide" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Deployment readiness</span>
                <h2>{readiness?.ready ? "Ready to move" : "Gated by proof debt"}</h2>
              </div>
              <StatusPill label="State" value={readiness?.ready ? "ready" : "blocked"} />
            </div>
            <div className="evidence-grid">
              <div className="evidence-card">
                <span>Runtime validation</span>
                <strong>{titleCase(readiness?.runtime_validation.status || "unknown")}</strong>
                <small>due {formatRelativeHours(readiness?.runtime_validation.due_in_hours)}</small>
              </div>
              <div className="evidence-card">
                <span>Target validation</span>
                <strong>{titleCase(readiness?.live_workload_target_validation.status || "unknown")}</strong>
                <small>age {formatRelativeHours(readiness?.live_workload_target_validation.age_hours)}</small>
              </div>
              <div className="evidence-card">
                <span>Workload proof</span>
                <strong>{titleCase(readiness?.live_workload_proof_validation.status || "unknown")}</strong>
                <small>age {formatRelativeHours(readiness?.live_workload_proof_validation.age_hours)}</small>
              </div>
              <div className="evidence-card">
                <span>Observability export</span>
                <strong>{titleCase(readiness?.observability_export_validation.status || "unknown")}</strong>
                <small>age {formatRelativeHours(readiness?.observability_export_validation.age_hours)}</small>
              </div>
            </div>
            <div className="issue-columns">
              <div>
                <h3>Blockers</h3>
                <ul className="signal-list">
                  {(readiness?.blockers.length ? readiness.blockers : ["No blocking signals."]).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h3>Warnings</h3>
                <ul className="signal-list">
                  {(readiness?.warnings.length ? readiness.warnings : ["No warning signals."]).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>
          </article>
        </section>

        <section className="horizontal-band command-panel-band" data-reveal>
          <article className="glass-panel band-panel">
            <div className="panel-header">
              <div>
                <span className="eyebrow">Analytics pulse</span>
                <h2>{titleCase(snapshot.analytics?.evaluation.status || "unknown")}</h2>
              </div>
              <small>{snapshot.analytics ? `${snapshot.analytics.window_days}d window` : "..."}</small>
            </div>
            <div className="mini-metrics">
              <div>
                <span>Pending debt</span>
                <strong>{formatCount(snapshot.analytics?.deployment_readiness.pending_change_control_count)}</strong>
              </div>
              <div>
                <span>Rejected debt</span>
                <strong>{formatCount(snapshot.analytics?.deployment_readiness.rejected_change_control_count)}</strong>
              </div>
              <div>
                <span>Audit anomalies</span>
                <strong>{formatCount(snapshot.analytics?.privileged_api_audit.non_ok_recent_entries)}</strong>
              </div>
            </div>
            <ul className="signal-list compact">
              {findings.slice(0, 6).map((finding) => (
                <li key={`${finding.code}-${finding.metric}`}>
                  <span className={`tone-chip tone-${statusTone(finding.severity)}`}>{finding.severity}</span>
                  <div>
                    <strong>{finding.code}</strong>
                    <p>{finding.summary}</p>
                  </div>
                </li>
              ))}
            </ul>
          </article>

          <article className="glass-panel band-panel">
            <div className="panel-header">
              <div>
                <span className="eyebrow">Runtime review queue</span>
                <h2>{formatCount(snapshot.reviews?.total_reviews)} open</h2>
              </div>
              <small>{formatCount(snapshot.reviews?.stale_unassigned_reviews)} stale unassigned</small>
            </div>
            <div className="table-wrap">
              <table className="signal-table">
                <colgroup>
                  <col className="col-summary-wide" />
                  <col className="col-tight" />
                  <col className="col-tight" />
                  <col className="col-tight" />
                </colgroup>
                <thead>
                  <tr>
                    <th>Summary</th>
                    <th>Owner</th>
                    <th>Status</th>
                    <th>Due</th>
                  </tr>
                </thead>
                <tbody>
                  {reviewRows.map((review) => (
                    <tr key={review.review_id}>
                      <td>
                        <div className="cell-stack">
                          <strong>{review.summary}</strong>
                          <small>{review.review_id.slice(0, 8)}</small>
                        </div>
                      </td>
                      <td>{review.owner_team || "unscoped"}</td>
                      <td>{titleCase(review.status)}</td>
                      <td>{formatRelativeHours(review.due_in_hours)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>

          <article className="glass-panel band-panel">
            <div className="panel-header">
              <div>
                <span className="eyebrow">Owner-team queue</span>
                <h2>{formatCount(snapshot.ownerQueue?.total_requests)} requests</h2>
              </div>
              <small>{formatCount(snapshot.ownerQueue?.rejected_count)} rejected</small>
            </div>
            <div className="table-wrap">
              <table className="signal-table">
                <colgroup>
                  <col className="col-summary-wide" />
                  <col className="col-tight" />
                  <col className="col-tight" />
                  <col className="col-tight" />
                </colgroup>
                <thead>
                  <tr>
                    <th>Summary</th>
                    <th>Owner</th>
                    <th>Status</th>
                    <th>Assignee</th>
                  </tr>
                </thead>
                <tbody>
                  {ownerRows.map((request) => (
                    <tr key={request.request_id}>
                      <td>
                        <div className="cell-stack">
                          <strong>{request.summary}</strong>
                          <small>{request.request_id.slice(0, 8)}</small>
                        </div>
                      </td>
                      <td>{request.owner_team || "unscoped"}</td>
                      <td>{titleCase(request.status)}</td>
                      <td>{request.assigned_to || "unassigned"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        </section>

        <section className="dashboard-grid">
          <article className="glass-panel wide" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Alert rail</span>
                <h2>Recent control-plane incidents</h2>
              </div>
              <small>{formatDate(snapshot.analytics?.generated_at)}</small>
            </div>
            <div className="alert-grid">
              {alertRows.map((alert) => (
                <button
                  className={`alert-card tone-${statusTone(alert.severity || alert.status)}`}
                  key={alert.alert_id}
                  onClick={() =>
                    runAction("Alert acknowledge", () =>
                      api.acknowledgeAlert(alert.alert_id, "acknowledged from command center"),
                    )
                  }
                  type="button"
                >
                  <span>{titleCase(alert.severity || "info")}</span>
                  <strong>{alert.summary}</strong>
                  <small>
                    {alert.owner_team || "global"} · {formatDate(alert.created_at)}
                  </small>
                </button>
              ))}
            </div>
          </article>
        </section>
      </main>
      <ApiConfigSheet open={configOpen} onClose={() => setConfigOpen(false)} />
    </div>
  );
}
