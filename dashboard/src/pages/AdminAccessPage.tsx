import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import CommandLayout from "../components/CommandLayout";
import { FEATURE_APPS, useAuth } from "../lib/auth";

type OAuthAppRecord = {
  appId: string;
  name: string;
  appUrl: string;
  description?: string;
  status: string;
};

type OAuthUserRecord = {
  name: string;
  username: string;
  email: string;
  role: string;
  projects: string[];
};

const REQUIRED_APPS: Array<{ appId: string; name: string; appUrl: string; description: string }> = [
  {
    appId: FEATURE_APPS.platform,
    name: "LSA Platform",
    appUrl: "http://127.0.0.1:1234/command",
    description: "Base product sign-in scope for Living Systems Auditor.",
  },
  {
    appId: FEATURE_APPS.reports,
    name: "LSA Reports Read",
    appUrl: "http://127.0.0.1:1234/command",
    description: "Read deployment readiness, trust score, incidents, proof bundles, and reports.",
  },
  {
    appId: FEATURE_APPS.targets,
    name: "LSA Targets Access",
    appUrl: "http://127.0.0.1:1234/targets",
    description: "Read and operate on live workload targets.",
  },
  {
    appId: FEATURE_APPS.reviews,
    name: "LSA Reviews Read",
    appUrl: "http://127.0.0.1:1234/command/reviews",
    description: "Read runtime validation reviews and review backlog data.",
  },
];

function normalizeApps(apps: string[]) {
  return [...new Set((apps || []).map((item) => String(item || "").trim().toLowerCase()).filter(Boolean))];
}

export default function AdminAccessPage() {
  const { oauthFetch, session } = useAuth();
  const [configOpen, setConfigOpen] = useState(false);
  const [users, setUsers] = useState<OAuthUserRecord[]>([]);
  const [apps, setApps] = useState<OAuthAppRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingUser, setSavingUser] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<"all" | "admin" | "user">("all");
  const [accessFilter, setAccessFilter] = useState<"all" | "reports" | "targets" | "reviews" | "none">("all");

  const load = async () => {
    setLoading(true);
    setMessage(null);
    const [appsPayload, usersPayload] = await Promise.all([
      oauthFetch<{ success: boolean; apps: OAuthAppRecord[] }>("/apps"),
      oauthFetch<{ success: boolean; users: OAuthUserRecord[] }>("/admin/users?limit=200"),
    ]);
    const existingIds = new Set((appsPayload.apps || []).map((app) => app.appId.trim().toLowerCase()));
    for (const app of REQUIRED_APPS) {
      if (existingIds.has(app.appId)) {
        continue;
      }
      await oauthFetch<{ success: boolean; app: OAuthAppRecord }>("/apps", {
        method: "POST",
        body: JSON.stringify(app),
      });
    }
    const refreshedApps = await oauthFetch<{ success: boolean; apps: OAuthAppRecord[] }>("/apps");
    setApps(refreshedApps.apps || []);
    setUsers(usersPayload.users || []);
    setLoading(false);
  };

  useEffect(() => {
    void load();
  }, []);

  const visibleApps = useMemo(
    () => REQUIRED_APPS.filter((app) => app.appId !== FEATURE_APPS.platform),
    [],
  );

  const filteredUsers = useMemo(() => {
    const search = searchQuery.trim().toLowerCase();

    return users.filter((user) => {
      const currentApps = normalizeApps(user.projects || []);
      const haystack = [user.name, user.username, user.email, user.role].join(" ").toLowerCase();

      if (search && !haystack.includes(search)) {
        return false;
      }

      if (roleFilter !== "all" && user.role !== roleFilter) {
        return false;
      }

      if (accessFilter === "none") {
        return !visibleApps.some((app) => currentApps.includes(app.appId));
      }

      if (accessFilter !== "all") {
        const featureAppId =
          accessFilter === "reports"
            ? FEATURE_APPS.reports
            : accessFilter === "targets"
              ? FEATURE_APPS.targets
              : FEATURE_APPS.reviews;
        return currentApps.includes(featureAppId);
      }

      return true;
    });
  }, [accessFilter, roleFilter, searchQuery, users, visibleApps]);

  const accessOverview = useMemo(() => {
    const userSummaries = users.map((user) => {
      const currentApps = normalizeApps(user.projects || []);
      return {
        admin: user.role === "admin",
        reports: currentApps.includes(FEATURE_APPS.reports),
        targets: currentApps.includes(FEATURE_APPS.targets),
        reviews: currentApps.includes(FEATURE_APPS.reviews),
      };
    });

    return {
      admins: userSummaries.filter((item) => item.admin).length,
      reports: userSummaries.filter((item) => item.reports).length,
      targets: userSummaries.filter((item) => item.targets).length,
      reviews: userSummaries.filter((item) => item.reviews).length,
    };
  }, [users]);

  return (
    <CommandLayout
      title="Access control"
      eyebrow="OAuth admin console"
      description="Grant reports, targets, and reviews access from the hosted OAuth app. User sessions inherit these scopes immediately on next sign-in."
      configOpen={configOpen}
      onOpenConfig={() => setConfigOpen(true)}
      onCloseConfig={() => setConfigOpen(false)}
      actions={
        <>
          <Link className="ghost-button" to="/admin/workspace">
            Open workspace
          </Link>
          <button className="primary-button" onClick={() => void load()} type="button">
            Refresh access
          </button>
        </>
      }
      meta={
        <div className="admin-access-summary">
          <article className="admin-access-stat featured">
            <span className="admin-access-stat-label">Session</span>
            <strong>{session?.username || "admin"}</strong>
            <small>Managing hosted OAuth grants and scoped product access.</small>
          </article>
          <article className="admin-access-stat">
            <span className="admin-access-stat-label">Directory</span>
            <strong>{users.length} users</strong>
            <small>{accessOverview.admins} admins with elevated controls.</small>
          </article>
          <article className="admin-access-stat">
            <span className="admin-access-stat-label">Surface grants</span>
            <strong>{accessOverview.targets + accessOverview.reports + accessOverview.reviews}</strong>
            <small>
              {accessOverview.reports} reports · {accessOverview.targets} targets · {accessOverview.reviews} reviews
            </small>
          </article>
          <article className="admin-access-stat">
            <span className="admin-access-stat-label">Provisioned apps</span>
            <strong>{apps.length} oauth apps</strong>
            <small>Core product scopes are provisioned automatically.</small>
          </article>
        </div>
      }
    >
      <section className="glass-panel" data-reveal>
        <div className="panel-heading">
          <div>
            <span className="eyebrow">App scopes</span>
            <h2>Provisioned OAuth application scopes</h2>
          </div>
        </div>
        <div className="table-wrap">
          <table className="signal-table">
            <thead>
              <tr>
                <th>App</th>
                <th>Route</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {REQUIRED_APPS.map((app) => {
                const match = apps.find((item) => item.appId === app.appId);
                return (
                  <tr key={app.appId}>
                    <td>
                      <div className="cell-stack">
                        <strong>{app.name}</strong>
                        <small>{app.appId}</small>
                      </div>
                    </td>
                    <td>{app.appUrl}</td>
                    <td>
                      <span className={`tone-chip ${match?.status === "active" ? "good" : "warn"}`}>
                        {match?.status || "missing"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="glass-panel" data-reveal>
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Users</span>
            <h2>Grant product surface access</h2>
          </div>
          {message ? <small>{message}</small> : null}
        </div>
        <div className="admin-access-toolbar">
          <label className="admin-access-search">
            <span>Search users</span>
            <input
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search by name, username, email, or role"
              type="search"
              value={searchQuery}
            />
          </label>
          <label className="admin-access-filter">
            <span>Role</span>
            <select value={roleFilter} onChange={(event) => setRoleFilter(event.target.value as typeof roleFilter)}>
              <option value="all">All roles</option>
              <option value="admin">Admins</option>
              <option value="user">Users</option>
            </select>
          </label>
          <label className="admin-access-filter">
            <span>Access</span>
            <select value={accessFilter} onChange={(event) => setAccessFilter(event.target.value as typeof accessFilter)}>
              <option value="all">All access states</option>
              <option value="reports">Reports enabled</option>
              <option value="targets">Targets enabled</option>
              <option value="reviews">Reviews enabled</option>
              <option value="none">No feature grants</option>
            </select>
          </label>
          <div className="admin-access-filter-result">
            <span className="admin-access-stat-label">Showing</span>
            <strong>
              {filteredUsers.length} / {users.length}
            </strong>
            <small>Search and filters apply instantly.</small>
          </div>
        </div>
        <div className="table-wrap">
          <table className="signal-table admin-access-table">
            <thead>
              <tr>
                <th className="col-summary-xxl">User</th>
                <th>Role</th>
                {visibleApps.map((app) => (
                  <th key={app.appId}>{app.name.replace("LSA ", "")}</th>
                ))}
                <th>Save</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((user) => {
                const currentApps = normalizeApps(user.projects || []);
                const stateKey = `access:${user.username}`;
                return (
                  <AdminUserRow
                    key={user.username}
                    busy={savingUser === stateKey}
                    user={user}
                    visibleApps={visibleApps}
                    currentApps={currentApps}
                    onSave={async (nextRole, requestedApps) => {
                      setSavingUser(stateKey);
                      setMessage(null);
                      try {
                        const finalApps = normalizeApps([FEATURE_APPS.platform, ...requestedApps]);
                        await oauthFetch(`/admin/users/${encodeURIComponent(user.username)}/apps`, {
                          method: "PUT",
                          body: JSON.stringify({ apps: finalApps }),
                        });
                        if (nextRole !== user.role) {
                          await oauthFetch(`/admin/role/${encodeURIComponent(user.username)}`, {
                            method: "PUT",
                            body: JSON.stringify({ role: nextRole }),
                          });
                        }
                        setMessage(`Updated ${user.username}`);
                        await load();
                      } finally {
                        setSavingUser(null);
                      }
                    }}
                  />
                );
              })}
              {!loading && users.length === 0 ? (
                <tr>
                  <td className="empty-row" colSpan={visibleApps.length + 3}>
                    No users returned from the OAuth admin API.
                  </td>
                </tr>
              ) : null}
              {!loading && users.length > 0 && filteredUsers.length === 0 ? (
                <tr>
                  <td className="empty-row" colSpan={visibleApps.length + 3}>
                    No users match the current search and filter settings.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </CommandLayout>
  );
}

function AdminUserRow({
  user,
  visibleApps,
  currentApps,
  onSave,
  busy,
}: {
  user: OAuthUserRecord;
  visibleApps: Array<{ appId: string; name: string }>;
  currentApps: string[];
  busy: boolean;
  onSave: (role: string, requestedApps: string[]) => Promise<void>;
}) {
  const [role, setRole] = useState(user.role);
  const [selectedApps, setSelectedApps] = useState<string[]>(currentApps);

  useEffect(() => {
    setRole(user.role);
    setSelectedApps(currentApps);
  }, [user.role, currentApps.join(",")]);

  const dirty = role !== user.role || normalizeApps(selectedApps).join(",") !== normalizeApps(currentApps).join(",");

  return (
    <tr>
      <td>
        <div className="cell-stack admin-access-user-cell">
          <strong>{user.name || user.username}</strong>
          <small>{user.username} · {user.email}</small>
          <div className="admin-access-user-tags">
            <span className={`tone-chip ${role === "admin" ? "good" : "neutral"}`}>{role}</span>
            {visibleApps
              .filter((app) => selectedApps.includes(app.appId))
              .map((app) => (
                <span className="tone-chip neutral" key={app.appId}>
                  {app.name.replace("LSA ", "")}
                </span>
              ))}
            {!visibleApps.some((app) => selectedApps.includes(app.appId)) ? (
              <span className="tone-chip warn">No feature grants</span>
            ) : null}
          </div>
        </div>
      </td>
      <td>
        <select value={role} onChange={(event) => setRole(event.target.value)}>
          <option value="user">user</option>
          <option value="admin">admin</option>
        </select>
      </td>
      {visibleApps.map((app) => {
        const enabled = selectedApps.includes(app.appId);
        return (
          <td key={app.appId}>
            <label className="checkbox-chip">
              <input
                checked={enabled}
                type="checkbox"
                onChange={(event) => {
                  setSelectedApps((current) => {
                    const next = new Set(current);
                    if (event.target.checked) {
                      next.add(app.appId);
                    } else {
                      next.delete(app.appId);
                    }
                    return [...next];
                  });
                }}
              />
              <span>{enabled ? "On" : "Off"}</span>
            </label>
          </td>
        );
      })}
      <td>
        <button
          className="ghost-button"
          disabled={!dirty || busy}
          onClick={() => void onSave(role, selectedApps)}
          type="button"
        >
          {busy ? "Saving..." : "Save"}
        </button>
      </td>
    </tr>
  );
}
