import { useMemo, useState } from "react";

import CommandLayout from "../components/CommandLayout";
import DetailDrawer from "../components/DetailDrawer";
import LiveStatusBadge from "../components/LiveStatusBadge";
import MetricCard from "../components/MetricCard";
import StatusPill from "../components/StatusPill";
import { useCommandSnapshot } from "../hooks/useCommandSnapshot";
import { useRevealMotion } from "../hooks/useRevealMotion";
import { formatDate, formatRelativeHours, statusTone, titleCase } from "../lib/format";
import type { RuntimeReview } from "../lib/types";

export default function RuntimeReviewsPage() {
  const [configOpen, setConfigOpen] = useState(false);
  const [selected, setSelected] = useState<RuntimeReview | null>(null);
  const { snapshot, loading, error, actionState } = useCommandSnapshot();

  useRevealMotion(".runtime-reviews-page", []);

  const pills = useMemo(
    () => [
      { label: "Backlog", value: String(snapshot.reviews?.total_reviews ?? 0) },
      { label: "Assigned", value: String(snapshot.reviews?.assigned_reviews ?? 0) },
      { label: "Unassigned", value: String(snapshot.reviews?.unassigned_reviews ?? 0) },
      { label: "Stale", value: String(snapshot.reviews?.stale_reviews ?? 0) },
    ],
    [snapshot.reviews],
  );

  return (
    <div className="runtime-reviews-page">
      <CommandLayout
        title="Runtime validation reviews"
        eyebrow="Review queue"
        description="Track proof debt as owned work, not hidden incident residue."
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
            label="Total reviews"
            value={snapshot.reviews?.total_reviews ?? 0}
            caption="All active runtime-proof review items."
          />
          <MetricCard
            label="Stale unassigned"
            value={snapshot.reviews?.stale_unassigned_reviews ?? 0}
            caption="The most expensive review debt."
            tone={(snapshot.reviews?.stale_unassigned_reviews ?? 0) > 0 ? "bad" : "good"}
          />
          <MetricCard
            label="Oldest age"
            value={snapshot.reviews?.oldest_review_age_hours ?? 0}
            caption="Hours since the oldest review opened."
            tone={(snapshot.reviews?.oldest_review_age_hours ?? 0) > 24 ? "warn" : "neutral"}
          />
        </section>

        <section className="dashboard-grid">
          <article className="glass-panel wide signal-accent-cyan" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Active reviews</span>
                <h2>Runtime-proof review backlog</h2>
              </div>
              <small>{snapshot.reviews?.environment_name || "default"}</small>
            </div>
            <div className="table-wrap">
              <table className="signal-table">
                <colgroup>
                  <col className="col-summary-xxl" />
                  <col className="col-tight" />
                  <col className="col-tight" />
                  <col className="col-tight" />
                  <col className="col-medium" />
                  <col className="col-tight" />
                  <col className="col-medium" />
                </colgroup>
                <thead>
                  <tr>
                    <th>Summary</th>
                    <th>Owner</th>
                    <th>Assignee</th>
                    <th>Status</th>
                    <th>Trigger</th>
                    <th>Due</th>
                    <th>Opened</th>
                  </tr>
                </thead>
                <tbody>
                  {(snapshot.reviews?.reviews ?? []).map((review) => (
                    <tr
                      className={`interactive-row ${selected?.review_id === review.review_id ? "is-selected" : ""}`}
                      key={review.review_id}
                      onClick={() => setSelected(review)}
                    >
                      <td>
                        <div className="cell-stack">
                          <strong>{review.summary}</strong>
                          <small>{review.review_id}</small>
                        </div>
                      </td>
                      <td>{review.owner_team || "unscoped"}</td>
                      <td>
                        <span className={`tone-chip tone-${review.assigned_to ? "good" : "warn"}`}>
                          {review.assigned_to || "unassigned"}
                        </span>
                      </td>
                      <td>
                        <span className={`tone-chip tone-${statusTone(review.status)}`}>
                          {titleCase(review.status)}
                        </span>
                      </td>
                      <td>
                        <div className="cell-stack">
                          <span className={`tone-chip tone-${statusTone(review.trigger_status)}`}>
                            {titleCase(review.trigger_status)}
                          </span>
                          <small>{titleCase(review.trigger_cadence_status)}</small>
                        </div>
                      </td>
                      <td>{formatRelativeHours(review.due_in_hours)}</td>
                      <td>{formatDate(review.opened_at)}</td>
                    </tr>
                  ))}
                  {!(snapshot.reviews?.reviews ?? []).length ? (
                    <tr>
                      <td className="empty-table-cell" colSpan={7}>
                        No runtime validation reviews are open.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </article>

          <article className="glass-panel wide signal-accent-mint" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Owner rollups</span>
                <h2>Which teams are carrying proof debt</h2>
              </div>
            </div>
            <div className="table-wrap">
              <table className="signal-table">
                <colgroup>
                  <col className="col-summary-wide" />
                  <col className="col-tight" />
                  <col className="col-tight" />
                  <col className="col-tight" />
                  <col className="col-tight" />
                </colgroup>
                <thead>
                  <tr>
                    <th>Owner team</th>
                    <th>Total</th>
                    <th>Assigned</th>
                    <th>Unassigned</th>
                    <th>Stale</th>
                  </tr>
                </thead>
                <tbody>
                  {(snapshot.reviews?.owner_team_rollups ?? []).map((rollup) => (
                    <tr key={rollup.owner_team}>
                      <td>{rollup.owner_team || "unscoped"}</td>
                      <td>{rollup.total_reviews}</td>
                      <td>{rollup.assigned_reviews}</td>
                      <td>{rollup.unassigned_reviews}</td>
                      <td>{rollup.stale_reviews}</td>
                    </tr>
                  ))}
                  {!(snapshot.reviews?.owner_team_rollups ?? []).length ? (
                    <tr>
                      <td className="empty-table-cell" colSpan={5}>
                        No owner-team review rollups yet.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </article>
        </section>
        <DetailDrawer
          open={Boolean(selected)}
          title={selected?.summary || "Review"}
          subtitle="Runtime review detail"
          onClose={() => setSelected(null)}
        >
          {selected ? (
            <div className="drawer-stack">
              <div className="detail-grid">
                <div><span>Review id</span><strong>{selected.review_id}</strong></div>
                <div><span>Status</span><strong>{titleCase(selected.status)}</strong></div>
                <div><span>Owner team</span><strong>{selected.owner_team || "unscoped"}</strong></div>
                <div><span>Assigned</span><strong>{selected.assigned_to || "unassigned"}</strong></div>
                <div><span>Trigger</span><strong>{titleCase(selected.trigger_status)}</strong></div>
                <div><span>Cadence</span><strong>{titleCase(selected.trigger_cadence_status)}</strong></div>
                <div><span>Due</span><strong>{formatRelativeHours(selected.due_in_hours)}</strong></div>
                <div><span>Opened</span><strong>{formatDate(selected.opened_at)}</strong></div>
              </div>
            </div>
          ) : null}
        </DetailDrawer>
      </CommandLayout>
    </div>
  );
}
