import { useMemo, useState } from "react";

import CommandLayout from "../components/CommandLayout";
import DetailDrawer from "../components/DetailDrawer";
import LiveStatusBadge from "../components/LiveStatusBadge";
import MetricCard from "../components/MetricCard";
import StatusPill from "../components/StatusPill";
import { useCommandSnapshot } from "../hooks/useCommandSnapshot";
import { useRevealMotion } from "../hooks/useRevealMotion";
import { formatDate, formatRelativeHours, statusTone, titleCase } from "../lib/format";
import type { ChangeControlRequest } from "../lib/types";

export default function DeploymentDebtPage() {
  const [configOpen, setConfigOpen] = useState(false);
  const [selected, setSelected] = useState<ChangeControlRequest | null>(null);
  const { snapshot, loading, error, actionState } = useCommandSnapshot();

  useRevealMotion(".deployment-debt-page", []);

  const readiness = snapshot.readiness;
  const pills = useMemo(
    () => [
      { label: "Ready", value: readiness?.ready ? "ready" : "blocked" },
      { label: "Blocked teams", value: String(readiness?.blocked_owner_team_count ?? 0) },
      { label: "Pending", value: String(snapshot.ownerQueue?.pending_review_count ?? 0) },
      { label: "Rejected", value: String(snapshot.ownerQueue?.rejected_count ?? 0) },
    ],
    [readiness, snapshot.ownerQueue],
  );

  return (
    <div className="deployment-debt-page">
      <CommandLayout
        title="Deployment readiness debt"
        eyebrow="Owner-team queue"
        description="Focus on the specific change-control debt blocking promotion, not generic dashboard noise."
        configOpen={configOpen}
        onOpenConfig={() => setConfigOpen(true)}
        onCloseConfig={() => setConfigOpen(false)}
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
        <section className="hero-status-row" data-stagger-group>
          {pills.map((item) => (
            <StatusPill key={item.label} label={item.label} value={item.value} />
          ))}
        </section>

        <section className="section-grid">
          <MetricCard
            label="Total requests"
            value={snapshot.ownerQueue?.total_requests ?? 0}
            caption="All deployment debt requests."
          />
          <MetricCard
            label="Assigned"
            value={snapshot.ownerQueue?.assigned_requests ?? 0}
            caption="Already owned by a human."
          />
          <MetricCard
            label="Oldest rejected age"
            value={readiness?.oldest_rejected_age_hours ?? 0}
            caption="Hours since the oldest rejected blocker."
            tone={(readiness?.oldest_rejected_age_hours ?? 0) > 24 ? "bad" : "neutral"}
          />
        </section>

        <section className="dashboard-grid">
          <article className="glass-panel wide signal-accent-pink" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Readiness blockers</span>
                <h2>Change-control debt linked to deployment readiness</h2>
              </div>
            </div>
            <div className="table-wrap">
              <table className="signal-table">
                <colgroup>
                  <col className="col-summary-xxl" />
                  <col className="col-tight" />
                  <col className="col-tight" />
                  <col className="col-tight" />
                  <col className="col-medium" />
                  <col className="col-medium" />
                  <col className="col-medium" />
                </colgroup>
                <thead>
                  <tr>
                    <th>Summary</th>
                    <th>Owner</th>
                    <th>Status</th>
                    <th>Assignee</th>
                    <th>Trigger</th>
                    <th>Opened</th>
                    <th>Resolved</th>
                  </tr>
                </thead>
                <tbody>
                  {(snapshot.ownerQueue?.requests ?? []).map((request) => (
                    <tr
                      className={`interactive-row ${selected?.request_id === request.request_id ? "is-selected" : ""}`}
                      key={request.request_id}
                      onClick={() => setSelected(request)}
                    >
                      <td>
                        <div className="cell-stack">
                          <strong>{request.summary}</strong>
                          <small>{request.request_id}</small>
                        </div>
                      </td>
                      <td>{request.owner_team || "unscoped"}</td>
                      <td>
                        <span className={`tone-chip tone-${statusTone(request.status)}`}>
                          {titleCase(request.status)}
                        </span>
                      </td>
                      <td>
                        <span className={`tone-chip tone-${request.assigned_to ? "good" : "warn"}`}>
                          {request.assigned_to || "unassigned"}
                        </span>
                      </td>
                      <td>
                        <span className="tone-chip tone-neutral">{titleCase(request.trigger_code)}</span>
                      </td>
                      <td>{formatDate(request.opened_at)}</td>
                      <td>{request.resolved_at ? formatDate(request.resolved_at) : "open"}</td>
                    </tr>
                  ))}
                  {!(snapshot.ownerQueue?.requests ?? []).length ? (
                    <tr>
                      <td className="empty-table-cell" colSpan={7}>
                        No deployment debt requests are open.
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
                <span className="eyebrow">Readiness reasons</span>
                <h2>Current blockers</h2>
              </div>
            </div>
            <ul className="signal-list">
              {(readiness?.blockers.length ? readiness.blockers : ["No blocking signals."]).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>

          <article className="glass-panel signal-accent-gold" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Warnings</span>
                <h2>Secondary pressure</h2>
              </div>
            </div>
            <ul className="signal-list">
              {(readiness?.warnings.length ? readiness.warnings : ["No warning signals."]).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        </section>
        <DetailDrawer
          open={Boolean(selected)}
          title={selected?.summary || "Change control"}
          subtitle="Deployment debt detail"
          onClose={() => setSelected(null)}
        >
          {selected ? (
            <div className="drawer-stack">
              <div className="detail-grid">
                <div><span>Request id</span><strong>{selected.request_id}</strong></div>
                <div><span>Status</span><strong>{titleCase(selected.status)}</strong></div>
                <div><span>Owner team</span><strong>{selected.owner_team || "unscoped"}</strong></div>
                <div><span>Assignee</span><strong>{selected.assigned_to || "unassigned"}</strong></div>
                <div><span>Trigger</span><strong>{titleCase(selected.trigger_code)}</strong></div>
                <div><span>Opened</span><strong>{formatDate(selected.opened_at)}</strong></div>
                <div><span>Resolved</span><strong>{selected.resolved_at ? formatDate(selected.resolved_at) : "open"}</strong></div>
                <div><span>Reason</span><strong>{selected.resolution_reason || "n/a"}</strong></div>
              </div>
            </div>
          ) : null}
        </DetailDrawer>
      </CommandLayout>
    </div>
  );
}
