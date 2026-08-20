import { useState } from "react";
import { Link } from "react-router-dom";

import CommandLayout from "../components/CommandLayout";
import { useRevealMotion } from "../hooks/useRevealMotion";

const journey = [
  {
    step: "01",
    route: "/",
    title: "Start on Signal",
    summary: "Understand what Living Systems Auditor does before touching controls.",
    why: "This page sells the mental model: intent, runtime truth, drift proof, and release confidence.",
    doNow: "Read the product story, scroll the architecture sections, then move to onboarding.",
  },
  {
    step: "02",
    route: "/onboarding",
    title: "Follow the operator path",
    summary: "Use this page as the canonical page-by-page workflow.",
    why: "Operators should not guess where to go next or what each page is for.",
    doNow: "Use each route below in order and check off the flow mentally.",
  },
  {
    step: "03",
    route: "/launch-guide",
    title: "Boot the stack",
    summary: "Run backend, run frontend, and understand split deploy basics.",
    why: "This page answers how to start, test, and deploy without reading source files.",
    doNow: "Run backend first, then frontend, then open the command center.",
  },
  {
    step: "04",
    route: "/login",
    title: "Sign in through OAuth",
    summary: "Use the hosted auth layer before opening protected operational surfaces.",
    why: "Roles and app scopes now drive what the operator can actually read or run.",
    doNow: "Sign in, then confirm whether your session has reports, targets, or reviews access.",
  },
  {
    step: "05",
    route: "/admin/access",
    title: "Grant access from admin console",
    summary: "Admins can turn reports, targets, and reviews access on for each user.",
    why: "This keeps the product understandable and limits each operator to the surface they actually need.",
    doNow: "As admin, ensure the LSA OAuth apps exist, then grant scopes to the right users.",
  },
  {
    step: "06",
    route: "/command",
    title: "Read system posture",
    summary: "Check health, readiness, cadence, and operator pressure.",
    why: "This is the heartbeat page. It tells you if the system is ready or blocked.",
    doNow: "Scan readiness, runtime cadence, target cadence, proof, reviews, debt, and alerts.",
  },
  {
    step: "07",
    route: "/targets",
    title: "Manage live targets",
    summary: "Define approved vs drift destinations and run real validation.",
    why: "Targets are where proof becomes real. This is how you test external systems.",
    doNow: "Pick `public-echo-pair` for a healthy demo or `public-failing-pair` for a failing demo, then run Validate.",
  },
  {
    step: "08",
    route: "/command/reviews",
    title: "Handle runtime reviews",
    summary: "Own runtime-proof review debt when cadence or rehearsal goes red.",
    why: "Runtime proof without ownership turns into ignored noise.",
    doNow: "Check stale or unassigned reviews and decide who should own them.",
  },
  {
    step: "09",
    route: "/command/deployment-debt",
    title: "Clear deployment blockers",
    summary: "See which teams or change-control items are stopping release.",
    why: "Release readiness is often blocked by policy, not code.",
    doNow: "Inspect blocked owner teams, rejected debt, and change-control state.",
  },
  {
    step: "10",
    route: "/command/incidents",
    title: "Read incidents",
    summary: "Inspect recent alerts and understand what the platform is trying to tell you.",
    why: "This is the incident lens for control-plane issues and drift proof failures.",
    doNow: "Review severity, state, and whether alerts came from runtime, readiness, or target validation.",
  },
  {
    step: "11",
    route: "/proof-bundles",
    title: "Export evidence",
    summary: "Package target proof, runtime proof, and operational evidence.",
    why: "Proof is only useful if it can be handed to another team, auditor, or release gate.",
    doNow: "Export a bundle after a green run, inspect it, then keep it as release evidence.",
  },
];

const fastLoop = [
  "Open /launch-guide and boot backend + frontend.",
  "Open /login and sign in through the hosted OAuth app.",
  "If you are admin, open /admin/access and grant reports, targets, and reviews scopes.",
  "Open /command and confirm health and deployment readiness are green.",
  "Open /targets and run Validate on public-echo-pair.",
  "Run Drift proof or Operational validation on a target.",
  "If red, read Target intel and AI explanation.",
  "Check /command/reviews and /command/incidents for follow-on governance.",
  "Export proof from /proof-bundles when the run is green.",
];

const failureLoop = [
  "Select public-failing-pair in /targets.",
  "Run Validate to force a red path.",
  "Read the AI explanation and supporting facts.",
  "Watch the target event graph and incident graph update.",
  "Open /command/incidents to see system-wide alert posture.",
];

export default function OnboardingPage() {
  const [configOpen, setConfigOpen] = useState(false);
  useRevealMotion(".onboarding-page", []);

  return (
    <div className="onboarding-page">
      <CommandLayout
        title="Page-by-page onboarding"
        eyebrow="Operator journey"
        description="A guided story for how a real operator should move through the app, why each page exists, and what to do next."
        configOpen={configOpen}
        onOpenConfig={() => setConfigOpen(true)}
        onCloseConfig={() => setConfigOpen(false)}
        actions={
          <>
            <Link className="primary-button" to="/command">
              Open Command Center
            </Link>
            <Link className="ghost-button" to="/targets">
              Go to Targets
            </Link>
          </>
        }
      >
        <section className="dashboard-grid">
          <article className="glass-panel wide signal-accent-cyan" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Operator flow</span>
                <h2>How to work with the application</h2>
                <small>Follow this in order the first time. After that, command and targets become your daily home.</small>
              </div>
            </div>
            <div className="onboarding-timeline">
              {journey.map((item) => (
                <Link className="onboarding-step-card" key={item.step} to={item.route}>
                  <div className="onboarding-step-top">
                    <span className="eyebrow">{item.step}</span>
                    <span className="tone-chip tone-neutral">{item.route}</span>
                  </div>
                  <strong>{item.title}</strong>
                  <p>{item.summary}</p>
                  <div className="onboarding-step-block">
                    <span>Why it exists</span>
                    <p>{item.why}</p>
                  </div>
                  <div className="onboarding-step-block">
                    <span>What to do</span>
                    <p>{item.doNow}</p>
                  </div>
                </Link>
              ))}
            </div>
          </article>

          <article className="glass-panel signal-accent-mint" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Green path</span>
                <h2>Fast loop</h2>
              </div>
            </div>
            <ol className="step-list">
              {fastLoop.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ol>
          </article>

          <article className="glass-panel signal-accent-gold" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Red path</span>
                <h2>Failure rehearsal</h2>
              </div>
            </div>
            <ol className="step-list">
              {failureLoop.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ol>
          </article>

          <article className="glass-panel signal-accent-violet" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Mental model</span>
                <h2>What each major page means</h2>
              </div>
            </div>
            <ul className="signal-list compact">
              <li>
                <p><strong>Signal</strong> is the narrative front door.</p>
              </li>
              <li>
                <p><strong>Launch guide</strong> is the runbook for boot and deploy.</p>
              </li>
              <li>
                <p><strong>Command</strong> is the posture board for the whole system.</p>
              </li>
              <li>
                <p><strong>Targets</strong> is where real external proof gets created and explained.</p>
              </li>
              <li>
                <p><strong>Reviews</strong> is ownership and cadence debt.</p>
              </li>
              <li>
                <p><strong>Deployment debt</strong> is release governance.</p>
              </li>
              <li>
                <p><strong>Incidents</strong> is the alert stream and incident lens.</p>
              </li>
              <li>
                <p><strong>Proof bundles</strong> is exportable release evidence.</p>
              </li>
            </ul>
          </article>
        </section>
      </CommandLayout>
    </div>
  );
}
