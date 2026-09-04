import { useCallback, useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";

import ApiConfigSheet from "../components/ApiConfigSheet";
import MetricCard from "../components/MetricCard";
import NavBar from "../components/NavBar";
import LiveStatusBadge from "../components/LiveStatusBadge";
import StatusPill from "../components/StatusPill";
import { useBackendApi } from "../lib/api";
import { formatDate } from "../lib/format";
import type { SessionReplayResponse, ReplayTimelineItem } from "../lib/types";

export default function IncidentReplayPage() {
  const api = useBackendApi();
  const [searchParams, setSearchParams] = useSearchParams();
  const [configOpen, setConfigOpen] = useState(false);
  const [sessionIdInput, setSessionIdInput] = useState(searchParams.get("sessionId") || "");
  const [replay, setReplay] = useState<SessionReplayResponse | null>(null);
  const [selectedItem, setSelectedItem] = useState<ReplayTimelineItem | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadReplay = useCallback(async (sid: string) => {
    if (!sid.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.getSessionReplay(sid.trim());
      setReplay(data);
      if (data.timeline.length > 0) {
        const firstDrift = data.timeline.find((t) => t.is_drift);
        setSelectedItem(firstDrift || data.timeline[0]);
      } else {
        setSelectedItem(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setReplay(null);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    const sid = searchParams.get("sessionId");
    if (sid) {
      setSessionIdInput(sid);
      loadReplay(sid);
    }
  }, [searchParams, loadReplay]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (sessionIdInput.trim()) {
      setSearchParams({ sessionId: sessionIdInput.trim() });
      loadReplay(sessionIdInput.trim());
    }
  };

  return (
    <div className="app-shell command-page">
      <NavBar onOpenConfig={() => setConfigOpen(true)} />
      <main style={{ padding: "2rem", maxWidth: "1400px", margin: "0 auto" }}>
        <section className="hero-grid compact" style={{ marginBottom: "2rem" }}>
          <div className="hero-copy">
            <span className="eyebrow">Interactive Incident Analysis</span>
            <h1>Agent Incident Replay</h1>
            <p>
              Compare declared intent against actual timestamped tool executions.
              Pinpoint the exact step where agent drifted, mutated out of bounds, or violated organization policy.
            </p>
            <div className="hero-status-row">
              <StatusPill label="Target Session" value={replay?.session_id || sessionIdInput || "none"} />
              <StatusPill label="Total Steps" value={replay ? String(replay.total_actions) : "0"} />
              <StatusPill
                label="Drift Points"
                value={replay ? String(replay.drift_points_count) : "0"}
              />
            </div>
            <div style={{ marginTop: "1rem" }}>
              <LiveStatusBadge loading={loading} idleLabel="Replay inspection engine ready" />
              {error ? <strong className="error-text" style={{ marginLeft: "1rem" }}>{error}</strong> : null}
            </div>
          </div>
        </section>

        {/* Search & Selector Bar */}
        <section style={{ marginBottom: "1.5rem", display: "flex", gap: "1rem", alignItems: "center" }}>
          <form onSubmit={handleSubmit} style={{ display: "flex", gap: "0.5rem", flex: 1, maxWidth: "600px" }}>
            <input
              type="text"
              placeholder="Enter Session ID to replay (e.g. dogfood-20260904-094000)..."
              value={sessionIdInput}
              onChange={(e) => setSessionIdInput(e.target.value)}
              style={{
                flex: 1,
                padding: "0.6rem 1rem",
                borderRadius: "6px",
                border: "1px solid var(--border-color, #333)",
                background: "rgba(255,255,255,0.05)",
                color: "inherit",
              }}
            />
            <button className="ghost-button" type="submit" style={{ padding: "0.6rem 1.2rem" }}>
              Load Replay
            </button>
          </form>
          <Link to="/sessions/events" className="ghost-button" style={{ padding: "0.6rem 1rem" }}>
            ← View Event Stream
          </Link>
          <Link to="/audit/would-it-catch" className="ghost-button" style={{ padding: "0.6rem 1rem" }}>
            Test Incident Rule →
          </Link>
        </section>

        {replay ? (
          <>
            <section className="section-grid" style={{ marginBottom: "2rem" }}>
              <MetricCard
                label="Declared Intent"
                value={replay.task_text.slice(0, 40) + (replay.task_text.length > 40 ? "..." : "")}
                caption={replay.task_text}
                tone="neutral"
              />
              <MetricCard
                label="Total Actions"
                value={replay.total_actions}
                caption="Recorded tool and shell actions."
                tone="good"
              />
              <MetricCard
                label="Drift Incidents"
                value={replay.drift_points_count}
                caption={replay.drift_points_count > 0 ? "Drift or violation points flagged." : "Clean session without drift."}
                tone={replay.drift_points_count > 0 ? "bad" : "good"}
              />
            </section>

            <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "2rem", alignItems: "start" }}>
              {/* Timeline list */}
              <div
                style={{
                  border: "1px solid var(--border-color, #333)",
                  borderRadius: "8px",
                  padding: "1.5rem",
                  background: "rgba(0,0,0,0.2)",
                }}
              >
                <h3 style={{ marginTop: 0, marginBottom: "1rem" }}>Action Timeline</h3>
                {replay.timeline.length === 0 ? (
                  <p style={{ color: "var(--muted, #888)" }}>No actions recorded for this session.</p>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                    {replay.timeline.map((item, idx) => {
                      const isSelected = selectedItem?.id === item.id;
                      const isDrift = item.is_drift;
                      return (
                        <div
                          key={item.id}
                          onClick={() => setSelectedItem(item)}
                          style={{
                            padding: "1rem",
                            borderRadius: "6px",
                            cursor: "pointer",
                            border: isSelected
                              ? "2px solid #3b82f6"
                              : isDrift
                              ? "1px solid #ef4444"
                              : "1px solid rgba(255,255,255,0.1)",
                            background: isDrift
                              ? "rgba(239, 68, 68, 0.12)"
                              : isSelected
                              ? "rgba(59, 130, 246, 0.12)"
                              : "rgba(255,255,255,0.02)",
                            transition: "all 0.15s ease",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.4rem" }}>
                            <span style={{ fontWeight: 600, fontSize: "0.9rem" }}>
                              #{idx + 1} {item.tool_name}
                            </span>
                            <span style={{ fontSize: "0.8rem", color: "var(--muted, #888)" }}>
                              {formatDate(item.created_at)}
                            </span>
                          </div>
                          <div
                            style={{
                              fontFamily: "monospace",
                              fontSize: "0.85rem",
                              wordBreak: "break-all",
                              color: isDrift ? "#fca5a5" : "#ddd",
                            }}
                          >
                            {item.target || "(no target specified)"}
                          </div>
                          {isDrift ? (
                            <div
                              style={{
                                marginTop: "0.5rem",
                                fontSize: "0.8rem",
                                color: "#ef4444",
                                fontWeight: 600,
                                display: "flex",
                                alignItems: "center",
                                gap: "0.4rem",
                              }}
                            >
                              <span>⚠️ DRIFT DETECTED:</span>
                              <span>{item.drift_reason}</span>
                            </div>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Action Inspector Panel */}
              <div
                style={{
                  border: "1px solid var(--border-color, #333)",
                  borderRadius: "8px",
                  padding: "1.5rem",
                  background: "rgba(0,0,0,0.2)",
                  position: "sticky",
                  top: "2rem",
                }}
              >
                <h3 style={{ marginTop: 0, marginBottom: "1rem" }}>Step Inspector</h3>
                {selectedItem ? (
                  <div>
                    <div style={{ marginBottom: "1rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                      <StatusPill label="Tool" value={selectedItem.tool_name} />
                      <StatusPill
                        label="Verdict"
                        value={selectedItem.is_drift ? "Drift Alert" : selectedItem.blocked ? "Blocked" : "Permitted"}
                      />
                      <StatusPill label="Agent" value={selectedItem.agent_source} />
                    </div>

                    <div style={{ marginBottom: "1rem" }}>
                      <label style={{ fontSize: "0.8rem", color: "var(--muted, #888)", display: "block" }}>
                        Executed Target / Command:
                      </label>
                      <pre
                        style={{
                          background: "#111",
                          padding: "0.75rem",
                          borderRadius: "4px",
                          overflowX: "auto",
                          fontSize: "0.85rem",
                          border: selectedItem.is_drift ? "1px solid #ef4444" : "1px solid #333",
                        }}
                      >
                        {selectedItem.target}
                      </pre>
                    </div>

                    {selectedItem.is_drift && (
                      <div
                        style={{
                          marginBottom: "1rem",
                          padding: "0.75rem",
                          background: "rgba(239, 68, 68, 0.15)",
                          border: "1px solid #ef4444",
                          borderRadius: "4px",
                        }}
                      >
                        <strong style={{ color: "#ef4444", display: "block", marginBottom: "0.25rem" }}>
                          Drift Classification
                        </strong>
                        <div style={{ fontSize: "0.85rem" }}>{selectedItem.drift_reason}</div>
                      </div>
                    )}

                    <div>
                      <label style={{ fontSize: "0.8rem", color: "var(--muted, #888)", display: "block" }}>
                        Raw Payload Context:
                      </label>
                      <pre
                        style={{
                          background: "#0d1117",
                          padding: "0.75rem",
                          borderRadius: "4px",
                          overflowX: "auto",
                          fontSize: "0.8rem",
                          maxHeight: "320px",
                        }}
                      >
                        {JSON.stringify(selectedItem.payload, null, 2)}
                      </pre>
                    </div>
                  </div>
                ) : (
                  <p style={{ color: "var(--muted, #888)" }}>Select an action from the timeline to inspect details.</p>
                )}
              </div>
            </div>
          </>
        ) : !loading && (
          <div
            style={{
              padding: "3rem",
              textAlign: "center",
              border: "1px dashed var(--border-color, #444)",
              borderRadius: "8px",
            }}
          >
            <h3>No session selected</h3>
            <p style={{ color: "var(--muted, #888)", maxWidth: "500px", margin: "0.5rem auto 1.5rem auto" }}>
              Enter a Session ID above or browse through recent telemetry in the Events tab to review an agent incident timeline.
            </p>
            <Link to="/sessions/events" className="ghost-button">
              Explore Live Sessions & Events
            </Link>
          </div>
        )}
      </main>
      <ApiConfigSheet open={configOpen} onClose={() => setConfigOpen(false)} />
    </div>
  );
}
