import { useEffect, useMemo, useState } from "react";

import CommandLayout from "../components/CommandLayout";
import DetailDrawer from "../components/DetailDrawer";
import MetricCard from "../components/MetricCard";
import { useBackendApi } from "../lib/api";
import { formatDate } from "../lib/format";
import type { ProofBundleInspection, ProofBundleRecord, TargetProfile } from "../lib/types";
import { useRevealMotion } from "../hooks/useRevealMotion";

export default function ProofBundlesPage() {
  const api = useBackendApi();
  const [configOpen, setConfigOpen] = useState(false);
  const [bundles, setBundles] = useState<ProofBundleRecord[]>([]);
  const [profiles, setProfiles] = useState<TargetProfile[]>([]);
  const [selected, setSelected] = useState<ProofBundleInspection | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionState, setActionState] = useState<string | null>(null);

  useRevealMotion(".proof-bundles-page", []);

  const load = async () => {
    setError(null);
    const [bundleList, profileList] = await Promise.all([api.getProofBundles(), api.getTargetProfiles()]);
    setBundles(bundleList);
    setProfiles(profileList);
  };

  useEffect(() => {
    load()
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const run = async (label: string, action: () => Promise<unknown>) => {
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
  };

  const enabledProfiles = useMemo(() => profiles.filter((profile) => profile.enabled), [profiles]);

  return (
    <div className="proof-bundles-page">
      <CommandLayout
        title="Proof bundles and target profiles"
        eyebrow="Evidence portability"
        description="Package live workload proof into portable artifacts and inspect the target profiles that drive external validation."
        configOpen={configOpen}
        onOpenConfig={() => setConfigOpen(true)}
        onCloseConfig={() => setConfigOpen(false)}
        actions={
          <button className="primary-button" onClick={() => run("Export proof bundle", () => api.exportProofBundle())} type="button">
            Export Proof Bundle
          </button>
        }
        meta={
          <>
            <span>{actionState || (loading ? "Loading bundle registry..." : "Portable proof and target registry")}</span>
            {error ? <strong className="error-text">{error}</strong> : null}
          </>
        }
      >
        <section className="section-grid">
          <MetricCard label="Bundles" value={bundles.length} caption="Exported portable proof artifacts." />
          <MetricCard label="Target profiles" value={profiles.length} caption="Built-in and file-backed external targets." />
          <MetricCard label="Enabled targets" value={enabledProfiles.length} caption="Profiles that can drive live proof right now." />
        </section>

        <section className="dashboard-grid">
          <article className="glass-panel wide" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Exported bundles</span>
                <h2>Portable live workload proof</h2>
              </div>
            </div>
            <div className="table-wrap">
              <table className="signal-table">
                <colgroup>
                  <col className="col-summary-xxl" />
                  <col className="col-medium" />
                  <col className="col-medium" />
                  <col className="col-tight" />
                </colgroup>
                <thead>
                  <tr>
                    <th>Bundle</th>
                    <th>Modified</th>
                    <th>Size</th>
                    <th>Inspect</th>
                  </tr>
                </thead>
                <tbody>
                  {bundles.map((bundle) => (
                    <tr key={bundle.path}>
                      <td>
                        <div className="cell-stack">
                          <strong>{bundle.file_name}</strong>
                          <small>{bundle.sha256.slice(0, 24)}...</small>
                        </div>
                      </td>
                      <td>{formatDate(bundle.modified_at)}</td>
                      <td>{Math.round(bundle.size_bytes / 1024)} KB</td>
                      <td>
                        <button
                          className="ghost-button small-button"
                          onClick={async () => setSelected(await api.inspectProofBundle(bundle.path))}
                          type="button"
                        >
                          Open
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>

          <article className="glass-panel wide" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Target registry</span>
                <h2>External workload proof profiles</h2>
              </div>
            </div>
            <div className="table-wrap">
              <table className="signal-table">
                <colgroup>
                  <col className="col-medium" />
                  <col className="col-summary-wide" />
                  <col className="col-summary-wide" />
                  <col className="col-tight" />
                </colgroup>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Approved target</th>
                    <th>Drift target</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {profiles.map((profile) => (
                    <tr key={profile.name}>
                      <td>
                        <div className="cell-stack">
                          <strong>{profile.name}</strong>
                          <small>{profile.enabled ? "enabled" : "disabled"}</small>
                        </div>
                      </td>
                      <td>{profile.approved_target_base_url}</td>
                      <td>{profile.drift_target_base_url}</td>
                      <td>{profile.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        </section>

        <DetailDrawer
          open={Boolean(selected)}
          title={selected?.file_name || "Bundle"}
          subtitle="Inspection"
          onClose={() => setSelected(null)}
        >
          {selected ? (
            <div className="drawer-stack">
              <div className="detail-grid">
                <div><span>Valid</span><strong>{selected.valid ? "yes" : "no"}</strong></div>
                <div><span>Environment</span><strong>{selected.environment_name || "default"}</strong></div>
                <div><span>Target profile</span><strong>{selected.target_profile || "unknown"}</strong></div>
                <div><span>Exported</span><strong>{selected.exported_at ? formatDate(selected.exported_at) : "n/a"}</strong></div>
              </div>
              <div className="drawer-code-block">
                <code>{selected.path}</code>
              </div>
              <ul className="signal-list">
                {(selected.blockers.length ? selected.blockers : ["No inspection blockers."]).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <button
                className="ghost-button"
                onClick={() => run("Delete proof bundle", async () => {
                  await api.deleteProofBundle(selected.path);
                  setSelected(null);
                })}
                type="button"
              >
                Delete bundle
              </button>
            </div>
          ) : null}
        </DetailDrawer>
      </CommandLayout>
    </div>
  );
}
