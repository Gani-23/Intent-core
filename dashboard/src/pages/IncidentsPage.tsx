import { useState } from "react";

import CommandLayout from "../components/CommandLayout";
import DetailDrawer from "../components/DetailDrawer";
import LiveStatusBadge from "../components/LiveStatusBadge";
import MetricCard from "../components/MetricCard";
import { useCommandSnapshot } from "../hooks/useCommandSnapshot";
import { useRevealMotion } from "../hooks/useRevealMotion";
import { formatCount, formatDate, formatRelativeHours, statusTone, titleCase } from "../lib/format";
import type { AlertRecord } from "../lib/types";

export default function IncidentsPage() {
  const [configOpen, setConfigOpen] = useState(false);
  const [selected, setSelected] = useState<AlertRecord | null>(null);
  const { snapshot, loading, error, actionState, runAction, api } = useCommandSnapshot();

  useRevealMotion(".incidents-page", []);

  return (
    <div className="incidents-page">
      <CommandLayout
        title="Incidents and proof evidence"
        eyebrow="Alert rail"
        description="Inspect the current alert stream beside the proof surfaces that are driving deployment gates."
        configOpen={configOpen}
        onOpenConfig={() => setConfigOpen(true)}
        onCloseConfig={() => setConfigOpen(false)}
        actions={
          <button
            className="primary-button"
            onClick={() => runAction("Emit alerts", () => api.emitAlerts())}
            type="button"
          >
            Emit Alerts
          </button>
        }
        meta={
          <>
            <LiveStatusBadge
              actionState={actionState}
              idleLabel="Live polling every 15s"
              loading={loading}
            />
            {error ? <strong className="error-text">{error}</strong> : null}
          </>
        }
      >
        <section className="section-grid">
          <MetricCard
            label="Incidents"
            value={snapshot.alerts.length}
            caption="Recent control-plane alerts."
          />
          <MetricCard
            label="Findings"
            value={snapshot.analytics?.evaluation.findings.length ?? 0}
            caption="Active analytics findings."
          />
          <MetricCard
            label="Target evidence age"
            value={snapshot.readiness?.live_workload_target_validation.age_hours ?? 0}
            caption="Hours since last target validation."
            tone={(snapshot.readiness?.live_workload_target_validation.age_hours ?? 0) > 18 ? "warn" : "good"}
          />
        </section>

        <section className="dashboard-grid">
          <article className="glass-panel wide signal-accent-pink" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Alert timeline</span>
                <h2>Recent incidents</h2>
              </div>
            </div>
            <div className="table-wrap">
              <table className="signal-table">
                <colgroup>
                  <col className="col-summary-alert" />
                  <col className="col-tight" />
                  <col className="col-tight" />
                  <col className="col-tight" />
                  <col className="col-medium" />
                  <col className="col-medium" />
                </colgroup>
                <thead>
                  <tr>
                    <th>Summary</th>
                    <th>Severity</th>
                    <th>Status</th>
                    <th>Owner</th>
                    <th>Created</th>
                    <th>Acknowledged</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshot.alerts.map((alert) => (
                    <tr
                      className={`interactive-row ${selected?.alert_id === alert.alert_id ? "is-selected" : ""}`}
                      key={alert.alert_id}
                      onClick={() => setSelected(alert)}
                    >
                      <td>
                        <div className="cell-stack">
                          <strong>{alert.summary}</strong>
                          <small>{alert.alert_key}</small>
                        </div>
                      </td>
                      <td>
                        <span className={`tone-chip tone-${statusTone(alert.severity)}`}>
                          {titleCase(alert.severity)}
                        </span>
                      </td>
                      <td>
                        <span className={`tone-chip tone-${statusTone(alert.status)}`}>
                          {titleCase(alert.status)}
                        </span>
                      </td>
                      <td>{alert.owner_team || "global"}</td>
                      <td>{formatDate(alert.created_at)}</td>
                      <td>{alert.acknowledged_at ? formatDate(alert.acknowledged_at) : "open"}</td>
                    </tr>
                  ))}
                  {!snapshot.alerts.length ? (
                    <tr>
                      <td className="empty-table-cell" colSpan={6}>
                        No recent incidents in the alert rail.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </article>

          <article className="glass-panel signal-accent-cyan" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Proof stack</span>
                <h2>Evidence freshness</h2>
              </div>
            </div>
            <ul className="signal-list">
              <li>
                <div>
                  <strong>Runtime validation</strong>
                  <p>
                    {titleCase(snapshot.readiness?.runtime_validation.status || "unknown")} · due{" "}
                    {formatRelativeHours(snapshot.readiness?.runtime_validation.due_in_hours)}
                  </p>
                </div>
              </li>
              <li>
                <div>
                  <strong>Target validation</strong>
                  <p>
                    {titleCase(snapshot.readiness?.live_workload_target_validation.status || "unknown")} · age{" "}
                    {formatRelativeHours(snapshot.readiness?.live_workload_target_validation.age_hours)}
                  </p>
                </div>
              </li>
              <li>
                <div>
                  <strong>Workload proof</strong>
                  <p>
                    {titleCase(snapshot.readiness?.live_workload_proof_validation.status || "unknown")} · age{" "}
                    {formatRelativeHours(snapshot.readiness?.live_workload_proof_validation.age_hours)}
                  </p>
                </div>
              </li>
              <li>
                <div>
                  <strong>Backup export</strong>
                  <p>
                    {titleCase(snapshot.readiness?.backup_export_validation.status || "unknown")} · age{" "}
                    {formatRelativeHours(snapshot.readiness?.backup_export_validation.age_hours)}
                  </p>
                </div>
              </li>
            </ul>
          </article>

          <article className="glass-panel signal-accent-gold" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Audit pressure</span>
                <h2>Privileged API anomalies</h2>
              </div>
            </div>
            <div className="mini-metrics">
              <div>
                <span>Recent</span>
                <strong>{formatCount(snapshot.analytics?.privileged_api_audit.recent_entries)}</strong>
              </div>
              <div>
                <span>Non-ok</span>
                <strong>{formatCount(snapshot.analytics?.privileged_api_audit.non_ok_recent_entries)}</strong>
              </div>
              <div>
                <span>Denied</span>
                <strong>{formatCount(snapshot.analytics?.privileged_api_audit.denied_recent_entries)}</strong>
              </div>
            </div>
          </article>
        </section>
        <DetailDrawer
          open={Boolean(selected)}
          title={selected?.summary || "Incident"}
          subtitle="Alert detail"
          onClose={() => setSelected(null)}
        >
          {selected ? (
            <div className="drawer-stack">
              <div className="detail-grid">
                <div><span>Alert id</span><strong>{selected.alert_id}</strong></div>
                <div><span>Severity</span><strong>{titleCase(selected.severity)}</strong></div>
                <div><span>Status</span><strong>{titleCase(selected.status)}</strong></div>
                <div><span>Owner</span><strong>{selected.owner_team || "global"}</strong></div>
                <div><span>Created</span><strong>{formatDate(selected.created_at)}</strong></div>
                <div><span>Acknowledged</span><strong>{selected.acknowledged_at ? formatDate(selected.acknowledged_at) : "open"}</strong></div>
              </div>
              <div className="drawer-code-block">
                <code>{selected.alert_key}</code>
              </div>
            </div>
          ) : null}
        </DetailDrawer>
      </CommandLayout>
    </div>
  );
}
