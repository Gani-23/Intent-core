import { useEffect, useRef } from "react";
import { Link, NavLink } from "react-router-dom";
import { animate } from "animejs";
import { useAuth } from "../lib/auth";

type Props = {
  onOpenConfig: () => void;
};

export default function NavBar({ onOpenConfig }: Props) {
  const ref = useRef<HTMLElement | null>(null);
  const { hasAnySession, hasPermission, isAdmin, session, logout } = useAuth();
  const links = [
    { to: "/", label: "Signal", end: true },
    { to: "/launch-guide", label: "Guide", end: true },
    { to: "/onboarding", label: "Onboard", end: true },
    ...(hasPermission("reports")
      ? [
          { to: "/proof-bundles", label: "Proof", end: true },
          { to: "/command", label: "Command", end: true },
          { to: "/command/deployment-debt", label: "Debt", end: true },
          { to: "/command/incidents", label: "Incidents", end: true },
        ]
      : []),
    ...(hasPermission("targets") ? [{ to: "/targets", label: "Targets", end: true }] : []),
    ...(hasPermission("reviews") ? [{ to: "/command/reviews", label: "Reviews", end: true }] : []),
    ...(isAdmin
      ? [
          { to: "/admin/access", label: "Access", end: true },
          { to: "/admin/secrets", label: "Secrets", end: true },
        ]
      : []),
    ...(hasPermission("workspace") ? [{ to: "/admin/workspace", label: "Workspace", end: true }] : []),
  ] as Array<{ to: string; label: string; end: boolean }>;

  useEffect(() => {
    if (!ref.current) {
      return;
    }
    animate(ref.current, {
      translateY: [-24, 0],
      opacity: [0, 1],
      duration: 1000,
      ease: "outExpo",
    });
  }, []);

  return (
    <header className="shell-nav" ref={ref}>
      <Link className="brand-mark" to="/">
        <span className="brand-dot" />
        <span>
          Living Systems
          <strong> Auditor</strong>
        </span>
      </Link>
      <nav className="nav-links">
        {links.map((link) => (
          <NavLink
            key={link.to}
            className={({ isActive }) => (isActive ? "active" : "")}
            end={link.end}
            to={link.to}
          >
            {link.label}
          </NavLink>
        ))}
      </nav>
      <div className="nav-actions">
        {hasAnySession ? <span className="status-pill neutral">{session?.username}</span> : null}
        {hasAnySession ? (
          <button className="ghost-button" onClick={logout} type="button">
            Logout
          </button>
        ) : (
          <Link className="ghost-button" to="/login">
            Login
          </Link>
        )}
        <button className="ghost-button" onClick={onOpenConfig} type="button">
          Auth Surface
        </button>
      </div>
    </header>
  );
}
