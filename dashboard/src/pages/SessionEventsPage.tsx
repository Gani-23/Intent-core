import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import ApiConfigSheet from "../components/ApiConfigSheet";
import MetricCard from "../components/MetricCard";
import NavBar from "../components/NavBar";
import LiveStatusBadge from "../components/LiveStatusBadge";
import StatusPill from "../components/StatusPill";
import { useBackendApi } from "../lib/api";
import { formatDate } from "../lib/format";
import type { HealthResponse, SessionEventRecord } from "../lib/types";

export default function SessionEventsPage() {
  const api = useBackendApi();
  const [configOpen, setConfigOpen] = useState(false);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [events, setEvents] = useState<SessionEventRecord[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<SessionEventRecord | null>(null);
  const [searchSessionId, setSearchSessionId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const h = await api.getHealth();
      setHealth(h);
      if (searchSessionId.trim()) {
        const evs = await api.getSessionEvents(searchSessionId.trim());
        setEvents(evs);
      } else {
        const evs = await api.getRecentSessionEvents(30);
        setEvents(evs);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [api, searchSessionId]);

  useEffect(() => {
    load();
  }, [load]);

  const uniqueSessions = Array.from(new Set(events.map((e) => e.session_id)));

  return (
    <div className="app-shell command-page">
      <NavBar onOpenConfig={() => setConfigOpen(true)} />
      <main style={{ padding: "2rem", maxWidth: "1400px", margin: "0 auto" }}>
        <section className="hero-grid compact" style={{ marginBottom: "2rem" }}>
          <div className="hero-copy">
            <span className="eyebrow">Real Telemetry Rail</span>
            <h1>Live Ingested Agent Sessions</h1>
            <p>
              Durable SQLite-backed agent tool events ingested live from Claude Code, Cursor, or Webhooks.
              Filtered strictly by caller authenticated organization identity.
            </p>
            <div className="hero-status-row">
              <StatusPill label="API Backend" value={health?.database_backend || "sqlite"} />
              <StatusPill label="Database State" value={health?.database_ready ? "connected" : "offline"} />
              <StatusPill label="Total Ingested" value={String(events.length)} />
              <StatusPill label="Active Sessions" value={String(uniqueSessions.length)} />
            </div>
            <div style={{ marginTop: "1rem" }}>
              <LiveStatusBadge loading={loading} idleLabel="Live SQLite telemetry ready" />
              {error ? <strong className="error-text" style={{ marginLeft: "1rem" }}>{error}</strong> : null}
            </div>
          </div>
        </section>

        <section className="section-grid" style={{ marginBottom: "2rem" }}>
          <MetricCard
            label="Ingested Events"
            value={events.length}
            caption="Events persisted in SQLite for current org."
            tone="good"
          />
          <MetricCard
            label="Unique Sessions"
            value={uniqueSessions.length}
            caption="Sessions monitored across agent runs."
            tone="neutral"
          />
          <MetricCard
            label="Database Backend"
            value={health?.database_backend || "sqlite"}
            caption="Real durability layer."
            tone={health?.database_ready ? "good" : "bad"}
          />
        </section>

        <section style={{ marginBottom: "1.5rem", display: "flex", gap: "1rem", alignItems: "center" }}>
          <input
            type="text"
            placeholder="Filter by Session ID (e.g. sess-1234)..."
            value={searchSessionId}
            onChange={(e) => setSearchSessionId(e.target.value)}
            style={{
              padding: "0.6rem 1rem",
              borderRadius: "8px",
              border: "1px solid rgba(255,255,255,0.2)",
              background: "rgba(0,0,0,0.4)",
              color: "#fff",
              width: "320px",
            }}
          />
          <button className="primary-button" onClick={load} type="button">
            Query Session
          </button>
          {searchSessionId && (
            <button
              className="ghost-button"
              onClick={() => setSearchSessionId("")}
              type="button"
            >
              Clear Filter
            </button>
          )}
        </section>

        <section className="dashboard-grid">
          <article className="glass-panel wide signal-accent-pink" style={{ padding: "1.5rem" }}>
            <div className="panel-header" style={{ marginBottom: "1rem" }}>
              <div>
                <span className="eyebrow">Durable Event Log</span>
                <h2>Ingested Events ({events.length})</h2>
              </div>
            </div>
            <div className="table-wrap">
              <table className="signal-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Session</th>
                    <th>Agent</th>
                    <th>Tool</th>
                    <th>Target / Command</th>
                    <th>Org</th>
                    <th>Timestamp</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((ev) => (
                    <tr
                      key={ev.id}
                      className={`interactive-row ${selectedEvent?.id === ev.id ? "is-selected" : ""}`}
                      onClick={() => setSelectedEvent(ev)}
                      style={{ cursor: "pointer" }}
                    >
                      <td><code>#{ev.id}</code></td>
                      <td><strong>{ev.session_id}</strong></td>
                      <td><span className="status-pill neutral">{ev.agent_source}</span></td>
                      <td><code>{ev.tool_name}</code></td>
                      <td>
                        <div className="cell-stack">
                          <strong>{ev.target || "(no target)"}</strong>
                        </div>
                      </td>
                      <td><small>{ev.organization_name}</small></td>
                      <td>{formatDate(ev.created_at)}</td>
                    </tr>
                  ))}
                  {!events.length && (
                    <tr>
                      <td colSpan={7} style={{ textAlign: "center", padding: "2rem" }}>
                        No session events found for this organization. Ingest events via /api/v1/sessions/events.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </article>

          {selectedEvent && (
            <article className="glass-panel" style={{ padding: "1.5rem" }}>
              <div className="panel-header">
                <div>
                  <span className="eyebrow">Inspection</span>
                  <h3>Event #{selectedEvent.id}</h3>
                </div>
                <button
                  className="ghost-button"
                  onClick={() => setSelectedEvent(null)}
                  type="button"
                >
                  Close
                </button>
              </div>
              <div style={{ marginTop: "1rem" }}>
                <p><strong>Session ID:</strong> {selectedEvent.session_id}</p>
                <p><strong>Agent Source:</strong> {selectedEvent.agent_source}</p>
                <p><strong>Tool:</strong> {selectedEvent.tool_name}</p>
                <p><strong>Target:</strong> {selectedEvent.target}</p>
                <p><strong>Organization:</strong> {selectedEvent.organization_name}</p>
                <p><strong>Recorded At:</strong> {selectedEvent.created_at}</p>
                <h4 style={{ marginTop: "1rem" }}>Redacted Payload</h4>
                <pre
                  style={{
                    background: "rgba(0,0,0,0.6)",
                    padding: "1rem",
                    borderRadius: "6px",
                    overflowX: "auto",
                    fontSize: "0.85rem",
                  }}
                >
                  {JSON.stringify(selectedEvent.payload, null, 2)}
                </pre>
              </div>
            </article>
          )}
        </section>
      </main>
      <ApiConfigSheet open={configOpen} onClose={() => setConfigOpen(false)} />
    </div>
  );
}
