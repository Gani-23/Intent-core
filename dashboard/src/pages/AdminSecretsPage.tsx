import { useEffect, useMemo, useState } from "react";

import CommandLayout from "../components/CommandLayout";
import { useBackendApi } from "../lib/api";
import type { SecretAlias } from "../lib/types";

const emptyForm = {
  alias: "",
  env_var_name: "",
  description: "",
  usage_scope: "",
};

function normalizeAlias(value: string) {
  return value.trim().toLowerCase().replace(/[\s-]+/g, "_");
}

function normalizeEnvVar(value: string) {
  return value.trim().toUpperCase().replace(/[\s-]+/g, "_");
}

function validateAlias(value: string) {
  if (!value) {
    return "Secret alias is required.";
  }
  if (!/^[a-z][a-z0-9_]*$/.test(value)) {
    return "Use lowercase letters, numbers, and underscores only, starting with a letter.";
  }
  return null;
}

function validateEnvVar(value: string) {
  if (!value) {
    return "Environment variable name is required.";
  }
  if (!/^[A-Z_][A-Z0-9_]*$/.test(value)) {
    return "Use uppercase letters, numbers, and underscores only, starting with a letter or underscore.";
  }
  return null;
}

export default function AdminSecretsPage() {
  const api = useBackendApi();
  const [configOpen, setConfigOpen] = useState(false);
  const [aliases, setAliases] = useState<SecretAlias[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);

  const load = async () => {
    setError(null);
    const next = await api.getSecretAliases();
    setAliases(next);
  };

  useEffect(() => {
    load()
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return aliases.filter((alias) => {
      if (!query) {
        return true;
      }
      return [
        alias.alias,
        alias.env_var_name,
        alias.description,
        alias.usage_scope,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query));
    });
  }, [aliases, search]);

  const summary = useMemo(
    () => ({
      total: aliases.length,
      present: aliases.filter((item) => item.present).length,
      missing: aliases.filter((item) => !item.present).length,
    }),
    [aliases],
  );

  const submit = async () => {
    setError(null);
    const alias = normalizeAlias(form.alias);
    const envVarName = normalizeEnvVar(form.env_var_name);
    const aliasError = validateAlias(alias);
    const envVarError = validateEnvVar(envVarName);
    if (aliasError || envVarError) {
      setError(aliasError || envVarError);
      return;
    }
    try {
      const saved = await api.upsertSecretAlias({
        alias,
        env_var_name: envVarName,
        description: form.description || null,
        usage_scope: form.usage_scope || null,
      });
      setMessage(`Saved ${saved.alias}`);
      setForm(emptyForm);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const remove = async (alias: string) => {
    setError(null);
    try {
      await api.deleteSecretAlias(alias);
      setMessage(`Deleted ${alias}`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <CommandLayout
      title="Secret aliases"
      eyebrow="Admin secret registry"
      description="Store env-backed secret references once, then use `secret:alias` in target headers and observability webhook headers."
      configOpen={configOpen}
      onOpenConfig={() => setConfigOpen(true)}
      onCloseConfig={() => setConfigOpen(false)}
      actions={
        <button className="primary-button" onClick={() => void load()} type="button">
          Refresh aliases
        </button>
      }
      meta={
        <>
          <span>{loading ? "Loading secret aliases..." : "Aliases resolve to environment variables at runtime."}</span>
          {error ? <strong className="error-text">{error}</strong> : null}
        </>
      }
    >
      <section className="section-grid">
        <div className="metric-card">
          <span className="metric-label">Aliases</span>
          <strong className="metric-value">{summary.total}</strong>
          <p className="metric-caption">Registered secret references.</p>
        </div>
        <div className="metric-card">
          <span className="metric-label">Present</span>
          <strong className="metric-value">{summary.present}</strong>
          <p className="metric-caption">Backed by a live environment variable.</p>
        </div>
        <div className="metric-card">
          <span className="metric-label">Missing</span>
          <strong className="metric-value">{summary.missing}</strong>
          <p className="metric-caption">Alias exists but the env var is not set.</p>
        </div>
      </section>

      <section className="dashboard-grid">
        <article className="glass-panel" data-reveal>
          <div className="panel-header">
            <div>
              <span className="eyebrow">Create alias</span>
              <h2>Map product references to environment variables</h2>
            </div>
            {message ? <small>{message}</small> : null}
          </div>
          <div className="targets-form">
            <label>
              <span>Alias</span>
              <input
                onChange={(event) => setForm((current) => ({ ...current, alias: event.target.value }))}
                placeholder="prod_api_token"
                value={form.alias}
              />
              <small className="field-hint">Lowercase slug. Example: <code>prod_api_token</code></small>
            </label>
            <label>
              <span>Environment variable</span>
              <input
                onChange={(event) => setForm((current) => ({ ...current, env_var_name: event.target.value }))}
                placeholder="PROD_API_TOKEN"
                value={form.env_var_name}
              />
              <small className="field-hint">Uppercase env var. Example: <code>PROD_API_TOKEN</code></small>
            </label>
            <label>
              <span>Usage scope</span>
              <input
                onChange={(event) => setForm((current) => ({ ...current, usage_scope: event.target.value }))}
                placeholder="targets, observability"
                value={form.usage_scope}
              />
            </label>
            <label>
              <span>Description</span>
              <input
                onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                placeholder="Bearer token for production status API"
                value={form.description}
              />
            </label>
            <button className="ghost-button" onClick={() => void submit()} type="button">
              Save alias
            </button>
            <p className="panel-copy">Example header JSON: {"{"}"Authorization":"Bearer secret:prod_api_token"{"}"}</p>
          </div>
        </article>

        <article className="glass-panel wide" data-reveal>
          <div className="panel-header">
            <div>
              <span className="eyebrow">Registry</span>
              <h2>Alias inventory</h2>
            </div>
          </div>
          <div className="filter-toolbar">
            <label className="filter-field filter-field-wide">
              <span>Search</span>
              <input
                onChange={(event) => setSearch(event.target.value)}
                placeholder="alias, env var, scope"
                type="search"
                value={search}
              />
            </label>
          </div>
          <div className="table-wrap">
            <table className="signal-table admin-access-table">
              <thead>
                <tr>
                  <th>Alias</th>
                  <th>Environment variable</th>
                  <th>Usage</th>
                  <th>Status</th>
                  <th>Updated</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {filtered.map((alias) => (
                  <tr key={alias.alias}>
                    <td>
                      <div className="cell-stack">
                        <strong>{alias.alias}</strong>
                        <small>{alias.description || "No description."}</small>
                      </div>
                    </td>
                    <td><code>{alias.env_var_name}</code></td>
                    <td>{alias.usage_scope || "general"}</td>
                    <td>
                      <span className={`tone-chip ${alias.present ? "good" : "warn"}`}>
                        {alias.present ? "present" : "missing"}
                      </span>
                    </td>
                    <td>{new Date(alias.updated_at).toLocaleString()}</td>
                    <td>
                      <button className="ghost-button small-button" onClick={() => void remove(alias.alias)} type="button">
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
                {!filtered.length ? (
                  <tr>
                    <td className="empty-row" colSpan={6}>
                      No secret aliases match the current query.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </CommandLayout>
  );
}
