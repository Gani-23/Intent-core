import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import NavBar from "../components/NavBar";
import { useAuth } from "../lib/auth";

export default function LoginPage() {
  const { login, loginAsLocalAdmin, ready, hasAnySession } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nextPath = useMemo(() => {
    const candidate = (location.state as { from?: string } | null)?.from;
    return candidate || "/command";
  }, [location.state]);

  useEffect(() => {
    if (ready && hasAnySession) {
      navigate(nextPath, { replace: true });
    }
  }, [ready, hasAnySession, navigate, nextPath]);

  const handleLocalAdminLogin = () => {
    loginAsLocalAdmin();
    navigate(nextPath, { replace: true });
  };

  return (
    <div className="auth-page">
      <div className="ambient-background home" />
      <NavBar onOpenConfig={() => {}} />
      <main className="auth-page-main">
        <section className="auth-card" data-reveal>
          <span className="eyebrow">Admin and operator login</span>
          <h1>Sign in through the hosted OAuth control plane.</h1>
          <p>
            Admins can grant reports, targets, and reviews access. Users inherit exactly the product surfaces the admin assigns.
          </p>

          <div style={{
            background: "rgba(16, 185, 129, 0.1)",
            border: "1px solid rgba(16, 185, 129, 0.3)",
            borderRadius: "12px",
            padding: "16px",
            marginBottom: "20px",
            display: "flex",
            flexDirection: "column",
            gap: "10px"
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#10b981", fontWeight: 600, fontSize: "0.95rem" }}>
              <span>⚡ Local Development Mode</span>
            </div>
            <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--muted-foreground, #94a3b8)", lineHeight: 1.4 }}>
              No password needed. Click below to immediately sign in as full local administrator with access to Command Center, Targets, Proof Bundles, Reviews, and all features.
            </p>
            <button
              type="button"
              className="primary-button"
              style={{
                background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                borderColor: "#10b981",
                color: "#ffffff",
                fontWeight: 600,
                width: "100%",
                padding: "12px 18px",
                cursor: "pointer"
              }}
              onClick={handleLocalAdminLogin}
            >
              Sign in as Local Admin (No Password Required)
            </button>
          </div>

          <div style={{ textAlign: "center", margin: "14px 0", color: "#64748b", fontSize: "0.85rem" }}>
            <span>— or sign in with credentials —</span>
          </div>

          <form
            className="auth-form"
            onSubmit={async (event) => {
              event.preventDefault();
              setSubmitting(true);
              setError(null);
              try {
                await login(email, password);
                navigate(nextPath, { replace: true });
              } catch (submitError) {
                setError(submitError instanceof Error ? submitError.message : "Sign in failed.");
              } finally {
                setSubmitting(false);
              }
            }}
          >
            <label>
              <span>Email</span>
              <input
                autoComplete="username"
                inputMode="email"
                placeholder="you@company.com"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <label>
              <span>Password</span>
              <input
                autoComplete="current-password"
                placeholder="••••••••••••"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            {error ? <div className="form-error">{error}</div> : null}
            <div className="hero-actions">
              <button className="ghost-button" disabled={submitting} type="submit">
                {submitting ? "Signing in..." : "Sign in with password"}
              </button>
              <Link className="ghost-button" to="/onboarding">
                Learn the flow
              </Link>
            </div>
          </form>
        </section>
      </main>
    </div>
  );
}
