import { useMemo } from "react";

import { useAuth } from "../lib/auth";
import { useApiConfig } from "../lib/api";

type Props = {
  open: boolean;
  onClose: () => void;
};

export default function ApiConfigSheet({ open, onClose }: Props) {
  const { config, updateConfig } = useApiConfig();
  const { session, hasAnySession, hasPermission, isAdmin } = useAuth();
  const title = useMemo(
    () =>
      `${hasAnySession ? (session?.role === "admin" ? "admin" : "operator") : (config.actorRole || "admin")} / ${config.actorTeam || "platform"} / ${config.actorOrganization || "default"}`,
    [config, hasAnySession, session?.role],
  );

  return (
    <div className={`sheet-backdrop ${open ? "open" : ""}`} onClick={onClose}>
      <aside
        className={`config-sheet ${open ? "open" : ""}`}
        onClick={(event) => event.stopPropagation()}
      >
        <form onSubmit={(event) => event.preventDefault()}>
          <div className="sheet-header">
            <div>
              <span className="eyebrow">Backend Identity</span>
              <h3>{title}</h3>
            </div>
            <button className="ghost-button" onClick={onClose} type="button">
              Close
            </button>
          </div>
          <label>
            API Key
            <input
              placeholder="optional"
              type="password"
              value={config.apiKey}
              onChange={(event) => updateConfig({ apiKey: event.target.value })}
            />
          </label>
          <div className="sheet-note">
            {hasAnySession ? (
              <>
                OAuth session: <strong>{session?.username}</strong> · {session?.role}
                <br />
                Access: reports {hasPermission("reports") ? "yes" : "no"} · targets {hasPermission("targets") ? "yes" : "no"} · reviews{" "}
                {hasPermission("reviews") ? "yes" : "no"} · admin {isAdmin ? "yes" : "no"}
              </>
            ) : (
              <>No OAuth session. Manual actor headers are active.</>
            )}
          </div>
          <label>
            Actor Id
            <input
              disabled={hasAnySession}
              value={config.actorId}
              onChange={(event) => updateConfig({ actorId: event.target.value })}
            />
          </label>
          <label>
            Actor Role
            <select
              disabled={hasAnySession}
              value={config.actorRole}
              onChange={(event) => updateConfig({ actorRole: event.target.value })}
            >
              <option value="admin">admin</option>
              <option value="operator">operator</option>
            </select>
          </label>
          <label>
            Actor Team
            <input
              value={config.actorTeam}
              onChange={(event) => updateConfig({ actorTeam: event.target.value })}
            />
          </label>
          <label>
            Actor Organization
            <input
              value={config.actorOrganization}
              onChange={(event) => updateConfig({ actorOrganization: event.target.value })}
            />
          </label>
          <p className="sheet-note">
            Protected FastAPI routes use the same actor headers the backend already expects. When OAuth is active, role and actor id are derived from the hosted session.
          </p>
        </form>
      </aside>
    </div>
  );
}
