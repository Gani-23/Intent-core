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
        label: "Release",
        value: "v1.0.2",
      },
      {
        label: "Marketplace",
        value: "Verified",
      },
      {
        label: "Diff Auditor",
        value: "Option B Active",
      },
      {
        label: "Test Suite",
        value: "102 Passed",
      },
    ],
    [],
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
              Runtime intent drift & PR safety gate for AI coding agents
            </span>
            <h1 data-hero-line>
              Most safety tools check permissions. We check whether
              <em> what the agent actually did still matches what you asked.</em>
            </h1>
            <p data-hero-line>
              The only safety check that catches an AI coding agent silently mutating secrets,
              wiping project directories, or tampering with CI workflows during a code freeze.
              Zero external pip dependencies.
            </p>
            <div className="hero-actions" data-hero-line>
              <a
                className="primary-button"
                href="https://github.com/marketplace/actions/intent-guard-pr-auditor"
                target="_blank"
                rel="noreferrer"
              >
                GitHub Marketplace
              </a>
              <Link className="ghost-button" to="/audit/would-it-catch">
                Would It Catch? Simulator
              </Link>
              <Link className="ghost-button" to="/command">
                Command Center
              </Link>
              <Link className="ghost-button" to="/launch-guide">
                Quickstart Guide
              </Link>
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
            <span>runtime intent</span>
            <span>pr safety gate</span>
            <span>drift detection</span>
            <span>destructive command blocking</span>
            <span>zero pip dependencies</span>
            <span>marketplace v1.0.2</span>
            <span>runtime intent</span>
            <span>pr safety gate</span>
            <span>drift detection</span>
            <span>destructive command blocking</span>
            <span>zero pip dependencies</span>
            <span>marketplace v1.0.2</span>
          </div>
        </section>

        <section className="section-grid">
          <MetricCard
            label="Audit Engine"
            value="Option B"
            caption="Dedicated static diff reviewer with zero false-positives on docs & comments."
            tone="good"
          />
          <MetricCard
            label="CI Runtime"
            value="~2s"
            caption="Ultra-fast execution with zero external pip dependencies."
            tone="good"
          />
          <MetricCard
            label="GitHub Marketplace"
            value="v1.0.2"
            caption="Verified action live on Marketplace with downloadable artifacts."
            tone="good"
          />
        </section>

        <section className="feature-band" data-reveal>
          <div>
            <span className="eyebrow">3-Line CI Drop-in</span>
            <h2>Zero-friction PR safety gate for autonomous coding agents.</h2>
          </div>
          <p>
            Drop Intent Guard into your GitHub Actions workflow in 3 lines. Every time Claude Code, Cursor,
            Devin, or an autonomous PR bot modifies code, Intent Guard verifies the diff against declared intent,
            flags unauthorized changes, and posts an idempotent sticky report directly on the PR.
          </p>
        </section>

        <section className="sticky-story" data-reveal>
          <div className="sticky-story-copy">
            <span className="eyebrow">Why it is needed</span>
            <h2>Most tools check who an agent is. Almost none check what it actually touched.</h2>
            <p>
              AI coding assistants already have write access in your codebase or runner. The real failure
              mode is semantic drift: an agent asked to fix a CSS bug silently touches an .env file,
              mutates deployment scripts, or wipes directories. Intent Guard is the deterministic guardrail.
            </p>
          </div>
          <div className="sticky-story-stack">
            <article className="story-stack-card">
              <strong>For engineering teams</strong>
              <p>Catch out-of-scope mutations and destructive commands before they ever hit main or review.</p>
            </article>
            <article className="story-stack-card">
              <strong>For security engineers</strong>
              <p>Enforce deterministic intent boundaries without trusting self-reported model explanations.</p>
            </article>
            <article className="story-stack-card">
              <strong>For platform operators</strong>
              <p>Zero-token runtime overhead, HMAC audit logs, and downloadable artifact proof bundles.</p>
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
                <span className="eyebrow">Quickstart</span>
                <h2>Fast path to real agent safety</h2>
              </div>
              <Link className="ghost-button" to="/launch-guide">
                Full guide
              </Link>
            </div>
            <div className="terminal-grid">
              <div className="terminal-panel">
                <span className="terminal-title">GitHub Actions (Marketplace)</span>
                <pre><code>{`# .github/workflows/intent-guard.yml
- uses: actions/checkout@v4
- uses: Gani-23/Intent-core@v1.0.2
  with:
    github_token: \${{ secrets.GH_TOKEN || github.token }}`}</code></pre>
              </div>
              <div className="terminal-panel">
                <span className="terminal-title">Claude Code Local Plugin</span>
                <pre><code>{`export CLAUDE_PLUGIN_ROOT="$(pwd)"
# Intercepts prompt & tool execution live
claude "Refactor auth in src/auth.py"`}</code></pre>
              </div>
              <div className="terminal-panel">
                <span className="terminal-title">Verification & Test Suite</span>
                <pre><code>{`.venv/bin/pytest tests/ -q
# 102 passed in 5.58s
# Option B static diff auditor active`}</code></pre>
              </div>
            </div>
          </article>
        </section>

        <section className="closing-cta" data-reveal>
          <span className="eyebrow">Zero pip dependencies · Production ready</span>
          <h2>Catch agent drift before your customers do.</h2>
          <p>
            From single-developer Claude Code sessions to autonomous enterprise PR bots,
            Intent Guard proves that AI agent execution strictly adhered to approved human intent.
          </p>
          <div className="hero-actions">
            <a
              className="primary-button"
              href="https://github.com/marketplace/actions/intent-guard-pr-auditor"
              target="_blank"
              rel="noreferrer"
            >
              Get on GitHub Marketplace
            </a>
            <Link className="ghost-button" to="/audit/would-it-catch">
              Try "Would It Catch?" Simulator
            </Link>
          </div>
        </section>
      </main>
      <ApiConfigSheet open={configOpen} onClose={() => setConfigOpen(false)} />
    </div>
  );
}
