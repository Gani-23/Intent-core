import { useState } from "react";

import CommandLayout from "../components/CommandLayout";
import { useRevealMotion } from "../hooks/useRevealMotion";

const backendBoot = `cd /Users/gani/Desktop/Intent-drive/living-systems-auditor
./.venv/bin/python -m uvicorn lsa.api.main:app --host 127.0.0.1 --port 3614`;

const frontendBoot = `cd /Users/gani/Desktop/Intent-drive/living-systems-auditor/dashboard
npm install
npm run dev -- --host 127.0.0.1 --port 1234`;

const proofChecks = `cd /Users/gani/Desktop/Intent-drive/living-systems-auditor
./.venv/bin/python -m lsa.cli.main control-plane-deployment-readiness
./.venv/bin/python -m lsa.cli.main run-control-plane-runtime-rehearsal --changed-by operator
./.venv/bin/python -m lsa.cli.main run-control-plane-operational-validation --changed-by operator`;

const splitDeploy = `# frontend
cp dashboard/.env.example dashboard/.env
# set VITE_API_BASE_URL=https://api.your-host

# backend
export LSA_API_ALLOWED_ORIGINS=https://frontend.your-host
./.venv/bin/python -m uvicorn lsa.api.main:app --host 0.0.0.0 --port 3614`;

function CodePanel({ title, code }: { title: string; code: string }) {
  return (
    <article className="glass-panel code-panel" data-reveal>
      <div className="panel-header">
        <div>
          <span className="eyebrow">{title}</span>
          <h2>{title}</h2>
        </div>
      </div>
      <pre>
        <code>{code}</code>
      </pre>
    </article>
  );
}

export default function LaunchGuidePage() {
  const [configOpen, setConfigOpen] = useState(false);

  useRevealMotion(".launch-guide-page", []);

  return (
    <div className="launch-guide-page">
      <CommandLayout
        title="Launch, test, and deploy"
        eyebrow="Field guide"
        description="Everything needed to boot the FastAPI backend, run the separate frontend, validate proof, and deploy the split system fast."
        configOpen={configOpen}
        onOpenConfig={() => setConfigOpen(true)}
        onCloseConfig={() => setConfigOpen(false)}
      >
        <section className="guide-grid">
          <CodePanel title="Run backend" code={backendBoot} />
          <CodePanel title="Run frontend" code={frontendBoot} />
          <CodePanel title="Core proof checks" code={proofChecks} />
          <CodePanel title="Split deploy" code={splitDeploy} />
        </section>

        <section className="dashboard-grid">
          <article className="glass-panel wide" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Why this app exists</span>
                <h2>Applications</h2>
              </div>
            </div>
            <div className="applications-grid">
              <div className="application-card">
                <strong>Release proof</strong>
                <p>Prove runtime, target, workload, backup, and observability evidence before promotion.</p>
              </div>
              <div className="application-card">
                <strong>Intent drift detection</strong>
                <p>Catch runtime behavior that departs from approved intent snapshots.</p>
              </div>
              <div className="application-card">
                <strong>Operator governance</strong>
                <p>Make reviews, ownership, change-control debt, and incidents visible in one place.</p>
              </div>
              <div className="application-card">
                <strong>Recovery confidence</strong>
                <p>Validate worker restart, lease takeover, queue recovery, and operational drills.</p>
              </div>
            </div>
          </article>

          <article className="glass-panel" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">How to test</span>
                <h2>Fast loop</h2>
              </div>
            </div>
            <ol className="step-list">
              <li>Boot backend.</li>
              <li>Boot frontend.</li>
              <li>Open `/command` and confirm health/readiness load.</li>
              <li>Run runtime rehearsal.</li>
              <li>Run operational validation.</li>
              <li>Check incidents/reviews if proof is red.</li>
            </ol>
          </article>

          <article className="glass-panel" data-reveal>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Why separate frontend</span>
                <h2>Operational reason</h2>
              </div>
            </div>
            <ul className="signal-list">
              <li>Frontend can ship faster without bloating FastAPI route files.</li>
              <li>Motion, 3D, and editorial UI stay isolated from backend logic.</li>
              <li>Split deploy becomes real through `VITE_API_BASE_URL` and backend CORS.</li>
              <li>The backend remains the source of truth; the frontend becomes the adoption layer.</li>
            </ul>
          </article>
        </section>
      </CommandLayout>
    </div>
  );
}
