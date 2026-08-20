import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { animate, stagger } from "animejs";

import ApiConfigSheet from "../components/ApiConfigSheet";
import MetricCard from "../components/MetricCard";
import NavBar from "../components/NavBar";
import ScrollProgressBar from "../components/ScrollProgressBar";
import ScrollMotionLayer from "../components/ScrollMotionLayer";
import StatusPill from "../components/StatusPill";
import { useScrollProgress } from "../hooks/useScrollProgress";
import { useScrollDriftMotion } from "../hooks/useScrollDriftMotion";
import { useBackendApi } from "../lib/api";
import { formatDate } from "../lib/format";
import type { HealthResponse } from "../lib/types";
import { useRevealMotion } from "../hooks/useRevealMotion";

const HeroScene = lazy(() => import("../components/HeroScene"));

function HeroFallback({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`hero-canvas hero-fallback-shell${compact ? " compact-fallback" : ""}`}>
      <div className="hero-fallback-orbit orbit-a" />
      <div className="hero-fallback-orbit orbit-b" />
      <div className="hero-fallback-orbit orbit-c" />
      <div className="hero-fallback-core">
        <div className="hero-fallback-glow" />
        <div className="hero-fallback-shape" />
      </div>
      <div className="hero-fallback-stars" />
    </div>
  );
}

export default function HomePage() {
  const [configOpen, setConfigOpen] = useState(false);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [enableHeroScene, setEnableHeroScene] = useState(false);
  const api = useBackendApi();
  const scrollProgress = useScrollProgress();

  useRevealMotion(".landing-page", []);
  useScrollDriftMotion("landing");

  useEffect(() => {
    api.getHealth().then(setHealth).catch((err) => setError(String(err)));
  }, [api]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const media = window.matchMedia("(prefers-reduced-motion: reduce), (max-width: 980px), (max-height: 720px)");
    const update = () => setEnableHeroScene(!media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    animate(".hero-copy [data-hero-line]", {
      opacity: [0, 1],
      translateY: [48, 0],
      delay: stagger(120),
      duration: 1200,
      ease: "outExpo",
    });
  }, []);

  const headlineMeta = useMemo(
    () => [
      {
        label: "Deployment",
        value: health?.deployment_readiness_ready ? "ready" : health?.status || "warming",
      },
      {
        label: "Runtime proof",
        value: health?.runtime_validation_status || "unknown",
      },
      {
        label: "Target proof",
        value: health?.live_workload_target_status || "unknown",
      },
      {
        label: "Workload proof",
        value: health?.live_workload_proof_status || "unknown",
      },
    ],
    [health],
  );

  return (
    <div className="app-shell landing-page">
      <div className="ambient-background" />
      <ScrollMotionLayer tone="landing" />
      <ScrollProgressBar progress={scrollProgress} />
      <NavBar onOpenConfig={() => setConfigOpen(true)} />
      <main>
        <section className="hero-grid">
          <div className="hero-copy">
            <span className="eyebrow" data-hero-line>
              Runtime intent. Deployment proof. Drift as signal.
            </span>
            <h1 data-hero-line>
              The control plane for software that needs to feel
              <em> alive, attributable, and undeniable.</em>
            </h1>
            <p data-hero-line>
              Separate frontend. FastAPI backend. Live readiness, proof cadence, governance debt,
              and recovery state in one fluid surface.
            </p>
            <div className="hero-actions" data-hero-line>
              <Link className="primary-button" to="/command">
                Enter Command Center
              </Link>
              <Link className="ghost-button" to="/launch-guide">
                Launch Guide
              </Link>
              <Link className="ghost-button" to="/proof-bundles">
                Proof Bundles
              </Link>
              <button className="ghost-button" type="button" onClick={() => setConfigOpen(true)}>
                Configure Backend Access
              </button>
            </div>
            <div className="hero-status-row" data-stagger-group>
              {headlineMeta.map((item) => (
                <StatusPill key={item.label} label={item.label} value={item.value} />
              ))}
            </div>
          </div>
          {enableHeroScene ? (
            <Suspense fallback={<HeroFallback compact />}>
              <HeroScene />
            </Suspense>
          ) : (
            <HeroFallback />
          )}
        </section>

        <section className="signal-marquee" data-reveal>
          <div className="signal-marquee-track">
            <span>runtime proof</span>
            <span>deployment readiness</span>
            <span>intent drift</span>
            <span>change-control debt</span>
            <span>incident attribution</span>
            <span>runtime proof</span>
            <span>deployment readiness</span>
            <span>intent drift</span>
            <span>change-control debt</span>
            <span>incident attribution</span>
          </div>
        </section>

        <section className="section-grid">
          <MetricCard
            label="Active workers"
            value={health?.active_workers ?? 0}
            caption="Live worker ownership visible from backend health."
            tone="good"
          />
          <MetricCard
            label="Queued jobs"
            value={health?.queued_jobs ?? 0}
            caption="Command center surfaces queue pressure immediately."
            tone={(health?.queued_jobs ?? 0) > 0 ? "warn" : "neutral"}
          />
          <MetricCard
            label="Running jobs"
            value={health?.running_jobs ?? 0}
            caption="Queue semantics already backed by the control plane."
          />
        </section>

        <section className="feature-band" data-reveal>
          <div>
            <span className="eyebrow">2026 UI direction</span>
            <h2>Editorial motion, cinematic depth, operator-grade signal.</h2>
          </div>
          <p>
            This frontend is no longer buried in FastAPI HTML strings. It is a separate Vite app,
            tuned for velocity, animated with anime.js, smoothed with Lenis, and staged for a real
            product shell.
          </p>
        </section>

        <section className="sticky-story" data-reveal>
          <div className="sticky-story-copy">
            <span className="eyebrow">Why it is needed</span>
            <h2>Most systems prove code. Almost none prove runtime intent.</h2>
            <p>
              Teams ship scanners, dashboards, and alert noise. They still struggle to answer the
              hard questions: did runtime behavior stay inside approved intent, do we have proof for
              promotion, who owns the debt, and can we trust recovery after failure.
            </p>
          </div>
          <div className="sticky-story-stack">
            <article className="story-stack-card">
              <strong>For platform teams</strong>
              <p>Track readiness, queue health, worker truth, backup proof, and cutover discipline.</p>
            </article>
            <article className="story-stack-card">
              <strong>For security</strong>
              <p>Watch runtime drift instead of only checking static policy before deploy.</p>
            </article>
            <article className="story-stack-card">
              <strong>For operators</strong>
              <p>Make review debt, escalation, and ownership visible before an incident explodes.</p>
            </article>
          </div>
        </section>

        <section className="story-grid">
          <article className="story-card" data-reveal>
            <span className="story-kicker">Proof Stack</span>
            <h3>Runtime, target, workload, backup, observability.</h3>
            <p>
              The backend already emits first-class readiness evidence. The frontend turns that
              into a surface people can actually use in a release room.
            </p>
          </article>
          <article className="story-card" data-reveal>
            <span className="story-kicker">Governance Debt</span>
            <h3>Reviews, ownership, alerts, and change-control debt.</h3>
            <p>
              No more hidden backlog. Teams see blocked owner queues, unresolved runtime proof, and
              escalation pressure in the same view.
            </p>
          </article>
          <article className="story-card" data-reveal>
            <span className="story-kicker">Backend Truth</span>
            <h3>FastAPI stays the source of truth.</h3>
            <p>
              This shell speaks directly to the existing control-plane contract, including protected
              actor-aware endpoints.
            </p>
          </article>
        </section>

        <section className="applications-showcase" data-reveal>
          <div className="applications-head">
            <span className="eyebrow">Applications</span>
            <h2>What this product is actually for.</h2>
          </div>
          <div className="applications-grid">
            <article className="application-card">
              <span className="story-kicker">Release rooms</span>
              <h3>Block promotion when proof is stale.</h3>
              <p>Runtime rehearsal, target validation, workload proof, backup proof, observability proof.</p>
            </article>
            <article className="application-card">
              <span className="story-kicker">Runtime safety</span>
              <h3>Catch drift on live behavior, not just code review.</h3>
              <p>Approved intent versus observed destinations, function impact, and attributable traces.</p>
            </article>
            <article className="application-card">
              <span className="story-kicker">Ops governance</span>
              <h3>Turn review debt into owned work.</h3>
              <p>Queues, incidents, owner-team debt, alerts, acknowledgements, and escalations.</p>
            </article>
            <article className="application-card">
              <span className="story-kicker">Recovery drills</span>
              <h3>Prove the control plane survives stress.</h3>
              <p>Worker restart, lease takeover, maintenance gating, backup restore, split-stack validation.</p>
            </article>
          </div>
        </section>

        <section className="proof-rail" data-reveal>
          <div className="proof-rail-copy">
            <span className="eyebrow">Instant pulse</span>
            <h2>Backend snapshot right now.</h2>
            <p>{error ? error : "Live health is pulled directly from the FastAPI backend."}</p>
          </div>
          <div className="proof-rail-panel">
            <div className="rail-row">
              <span>Environment</span>
              <strong>{health?.environment_name ?? "default"}</strong>
            </div>
            <div className="rail-row">
              <span>Database</span>
              <strong>{health?.database_backend ?? "unknown"}</strong>
            </div>
            <div className="rail-row">
              <span>Worker mode</span>
              <strong>{health?.worker_mode ?? "unknown"}</strong>
            </div>
            <div className="rail-row">
              <span>Updated</span>
              <strong>{formatDate(new Date().toISOString())}</strong>
            </div>
          </div>
        </section>

        <section className="architecture-band" data-reveal>
          <div className="architecture-copy">
            <span className="eyebrow">Architecture</span>
            <h2>Separate frontend, FastAPI backend, one control-plane contract.</h2>
            <p>
              The frontend is the adoption layer. FastAPI remains the proof engine and control
              plane. This split keeps motion-heavy UI fast while leaving runtime truth in Python.
            </p>
          </div>
          <div className="architecture-layers">
            <div className="layer-card">
              <strong>Frontend</strong>
              <p>Vite, React, anime.js, Lenis, React Three Fiber.</p>
            </div>
            <div className="layer-card">
              <strong>Backend</strong>
              <p>FastAPI APIs for health, readiness, analytics, queues, alerts, proofs, and drills.</p>
            </div>
            <div className="layer-card">
              <strong>Control plane</strong>
              <p>Snapshots, audits, jobs, workers, leases, reviews, governance, cutover, backup, observability.</p>
            </div>
          </div>
        </section>

        <section className="parallax-showcase" data-reveal>
          <div className="parallax-copy">
            <span className="eyebrow">Scroll choreography</span>
            <h2>Motion should tell you what matters before text does.</h2>
            <p>
              Inspired by premium narrative sites, this surface uses layered depth instead of dead
              panels. As you scroll, proof, governance, and workload layers drift at different
              speeds so the product feels like a live system, not a flat report.
            </p>
          </div>
          <div className="parallax-stage">
            <article className="parallax-card card-runtime">
              <span className="story-kicker">Runtime proof</span>
              <strong>Fresh cadence, visible drift, attributable state.</strong>
              <p>Proof layers float in front because runtime truth is the first thing release rooms care about.</p>
            </article>
            <article className="parallax-card card-governance">
              <span className="story-kicker">Governance debt</span>
              <strong>Reviews, ownership, and change-control pressure.</strong>
              <p>Debt sits on a different motion plane so blocked ownership feels present, not buried.</p>
            </article>
            <article className="parallax-card card-targets">
              <span className="story-kicker">Live targets</span>
              <strong>Target reachability, workload proof, recovery confidence.</strong>
              <p>External proof stays in motion because production trust decays if evidence goes stale.</p>
            </article>
          </div>
        </section>

        <section className="guide-preview-grid">
          <article className="glass-panel wide" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">How to test</span>
                <h2>Fast path from clone to proof</h2>
              </div>
              <Link className="ghost-button" to="/launch-guide">
                Full guide
              </Link>
            </div>
            <div className="terminal-grid">
              <div className="terminal-panel">
                <span className="terminal-title">Backend</span>
                <pre><code>{`cd /Users/gani/Desktop/Intent-drive/living-systems-auditor
./.venv/bin/python -m uvicorn lsa.api.main:app --host 127.0.0.1 --port 3614`}</code></pre>
              </div>
              <div className="terminal-panel">
                <span className="terminal-title">Frontend</span>
                <pre><code>{`cd /Users/gani/Desktop/Intent-drive/living-systems-auditor/dashboard
npm install
npm run dev -- --host 127.0.0.1 --port 1234`}</code></pre>
              </div>
              <div className="terminal-panel">
                <span className="terminal-title">Proof</span>
                <pre><code>{`./.venv/bin/python -m lsa.cli.main control-plane-deployment-readiness
./.venv/bin/python -m lsa.cli.main run-control-plane-operational-validation --changed-by operator`}</code></pre>
              </div>
            </div>
          </article>
        </section>

        <section className="closing-cta" data-reveal>
          <span className="eyebrow">Industry-shaping direction</span>
          <h2>Make runtime proof feel like a product, not a postmortem artifact.</h2>
          <p>
            The shock factor won’t come from glow alone. It comes from a frontend that feels elite
            and a backend that can actually prove something when the lights are on.
          </p>
          <div className="hero-actions">
            <Link className="primary-button" to="/command">
              Open the control plane
            </Link>
            <Link className="ghost-button" to="/launch-guide">
              Read launch guide
            </Link>
          </div>
        </section>
      </main>
      <ApiConfigSheet open={configOpen} onClose={() => setConfigOpen(false)} />
    </div>
  );
}
