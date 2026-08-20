import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import NavBar from "../components/NavBar";
import { useAuth } from "../lib/auth";

export default function LoginPage() {
  const { login, ready, hasAnySession } = useAuth();
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
              <button className="primary-button" disabled={submitting} type="submit">
                {submitting ? "Signing in..." : "Sign in"}
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
