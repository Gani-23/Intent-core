import type { PropsWithChildren } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";

import type { AuthPermission } from "../lib/auth";
import { useAuth } from "../lib/auth";

type Props = PropsWithChildren<{
  permission: AuthPermission;
}>;

export default function ProtectedRoute({ permission, children }: Props) {
  const { ready, hasAnySession, hasPermission } = useAuth();
  const location = useLocation();

  if (!ready) {
    return <div className="route-loading">Loading access surface...</div>;
  }

  if (!hasAnySession) {
    return <Navigate replace state={{ from: location.pathname }} to="/login" />;
  }

  if (!hasPermission(permission)) {
    return (
      <div className="auth-page">
        <div className="ambient-background command" />
        <main className="auth-page-main">
          <section className="auth-card" data-reveal>
            <span className="eyebrow">Access blocked</span>
            <h1>This session does not have {permission} access.</h1>
            <p>Ask an administrator to grant this permission from the access console.</p>
            <div className="hero-actions">
              <Link className="ghost-button" to="/command">
                Back to command
              </Link>
            </div>
          </section>
        </main>
      </div>
    );
  }

  return <>{children}</>;
}
