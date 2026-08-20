# Living Systems Auditor Checkpoint

Date: 2026-06-11

Use this file as the first context reload on a new machine. It summarizes the current product state, what is already proven, what is left to harden, and the most valuable next work.

## 1) Current State

This project is now a real control-plane product, not a prototype.

### Backend

- Python FastAPI backend with a real control plane.
- Supports SQLite for local/dev and Postgres for production.
- Runtime proof surfaces are implemented:
  - runtime rehearsal
  - live workload target validation
  - live workload drift proof
  - live workload proof bundles
  - operational validation
  - backup rehearsal/validation/export
  - observability export validation
  - soak validation
  - queue/workload/worker recovery drills
  - trust score
  - incident narrative
  - canary verification
- Control-plane data model includes:
  - targets
  - reviews
  - incidents
  - alerts
  - silences
  - change-control
  - governance requests
  - maintenance events
  - backups
  - proof bundles
  - organization/team/project/workspace records
  - assignments and comments
- OAuth login is wired in.
- Admin and workspace access controls exist.
- Secret aliases exist and are env-backed.
- Target profiles support:
  - org/team/project/environment scoping
  - custom validation/proof URLs
  - custom HTTP methods
  - custom headers
  - expected status codes
  - timeout configuration
  - env-backed header values using `env:NAME`
  - env-backed secret aliases using `secret:alias`

### Frontend

- Separate Vite + React frontend.
- Main areas:
  - home
  - onboarding
  - launch guide
  - command center
  - targets
  - runtime reviews
  - deployment debt
  - incidents
  - proof bundles
  - admin access
  - admin workspace
  - admin secrets
  - login
- UI is intentionally premium/modern with motion and responsive behavior.
- Heavy `three.js` production dependency was removed from the shipped hero; hero is now lightweight.

### Auth / Access

- Hosted OAuth app at `https://oauth4-0.onrender.com` is integrated.
- Admin login and scope grants are available.
- Product permissions currently include:
  - reports
  - targets
  - reviews
  - admin
  - workspace

### Current Data/Artifact Reality

- `data/` contains a lot of generated runtime evidence.
- Biggest growth source was backup archives in `data/control_plane_backups/`.
- Those backups must stay out of Git.
- A prior cleanup reduced the backups to a small rolling set, but the app still generates runtime evidence files during proof runs.

## 2) What Is Already Proven

These have been run successfully in this repository:

- runtime validation
- target validation
- drift proof
- canary verify
- operational validation
- backup rehearsal
- backup export validation
- observability export validation
- queue validation
- workload validation
- worker recovery validation
- soak validation
- live local stack proof
- live AWS proof
- constrained Docker proof
- local and live external target demonstrations
- AI remediation/explanation path using Gemini-compatible provider config

## 3) What the App Is For

The app is a runtime governance and proof system.

It is meant to answer:

- Can we trust this environment right now?
- Are proofs fresh?
- Is runtime drift present?
- Are backups valid?
- Are targets behaving as expected?
- Is deployment readiness blocked?
- Who owns the problem?
- What changed?
- What should happen next?

## 4) Important Product Structure

### Core Surfaces

- `command`:
  - system posture
  - trust score
  - incident narrative
  - readiness
  - review/debt queues
  - alert stream
- `targets`:
  - target registry
  - validation/proof actions
  - target intel
  - graphs
  - AI explanation panel
- `admin/access`:
  - OAuth app scope provisioning
  - user access grants
- `admin/workspace`:
  - organization/team/project/membership management
  - assignment lifecycle
  - removal ledger
  - workspace operations
- `admin/secrets`:
  - env-backed secret aliases

### Workspace/Org Layer

The org layer exists, but it is still not fully expanded across every historical record.

Current workspace model includes:

- organization
- team
- project
- membership
- removal ledger
- assignment
- assignment comments
- scoped target profiles
- scoped soak telemetry

## 5) Known Gaps Left

This is the honest remaining hardening list.

### Highest Priority Gaps

1. Secret lifecycle hardening
   - secret aliases are env-backed, not a real encrypted vault
   - needs secure storage if target credentials become serious production secrets

2. Deeper org isolation
   - extend org/team/project scoping across more historical records
   - especially incidents, reviews, proofs, maintenance history, and audit history

3. Public-launch authz review
   - route-by-route security review
   - ensure admin/workspace/target mutation flows are locked down correctly

4. External proof breadth
   - more customer-like targets
   - more realistic deployed environments
   - external observability sinks in a real environment

5. Final frontend polish
   - admin/workspace consistency
   - error-state polish
   - remaining UX cleanup

### Medium Priority Gaps

- backup retention policy should be more explicit and capped
- log/trace pruning should be more automated
- release packaging and operator runbooks could be cleaner
- better long-run soak scheduling on real infra
- more docs for onboarding, ops, and recovery

## 6) Next State

If continuing the project from this checkpoint, the best next sequence is:

1. Secure secret storage
   - move from env-backed aliases to a real encrypted secret store or secret manager abstraction

2. Expand org isolation
   - make every core record org/team/project-aware

3. Tighten authz
   - review all admin/workspace/targets/review mutation routes
   - make permissions explicit and testable

4. Improve runtime evidence hygiene
   - enforce backup retention
   - clean old evidence files automatically
   - keep only a rolling window of archives and logs

5. Push external proof
   - customer-like real targets
   - real deploy environments
   - real observability integrations

6. Final frontend cleanup
   - polish the newest admin/workspace surfaces
   - improve error visibility and hierarchy

## 7) Future Goals

These are the strongest product expansions if you want this to become breakout-grade.

### Org / Team / Project Productization

- Jira-like assignment flows
- manager/admin roles with explicit scope boundaries
- user suspension/removal ledger with reason and actor history
- per-project dashboards
- team/project ownership on reviews/incidents/targets
- comments and threaded activity on assignments and incidents

### Runtime Governance Differentiators

- intent contract learning
- drift replay sandbox
- root-cause graph
- autonomous canary verifier
- one-click remediation plans
- change-impact forecasting
- trust scoring by service/environment/team/project

### Operator Experience

- incident timeline/story view
- release gating like Bamboo
- work queue views like Jira
- assign monitoring and reviews to named owners
- per-team SLA clocks
- escalation ladders

### Proof / Validation

- long multi-hour soak
- repeated scheduled soak runs
- noisy live workloads
- target-specific proofs with custom auth
- public and customer-like external targets

## 8) Improvements Worth Doing

- Add a real secret vault abstraction.
- Add backup retention and automatic pruning.
- Add explicit rotation for generated evidence files.
- Add more search/filtering in admin/workspace views for large orgs.
- Add better empty states and failure states to target intel and workspace pages.
- Add export/import for target profiles and workspace templates.
- Add webhooks/notifications for assignment and incident ownership changes.
- Add per-user workload and ownership views.

## 9) Local Run Notes

Backend:

```bash
cd /Users/gani/Desktop/Intent-drive/living-systems-auditor
bash scripts/run_local_backend.sh
```

Split stack:

```bash
cd /Users/gani/Desktop/Intent-drive/living-systems-auditor
bash scripts/run_local_stack.sh --testing
```

Frontend:

```bash
cd /Users/gani/Desktop/Intent-drive/living-systems-auditor/dashboard
npm run dev -- --host 127.0.0.1 --port 1234
```

Useful pages:

- `http://127.0.0.1:3614/health`
- `http://127.0.0.1:1234/`
- `http://127.0.0.1:1234/command`
- `http://127.0.0.1:1234/targets`
- `http://127.0.0.1:1234/admin/access`
- `http://127.0.0.1:1234/admin/workspace`
- `http://127.0.0.1:1234/admin/secrets`

## 10) Transfer Notes For New Machine

When moving this repo to another PC:

- do not commit `.env.local`
- do not commit `.venv`
- do not commit `dashboard/node_modules`
- do not commit `dashboard/dist`
- do not commit `data/` runtime artifacts
- do not commit `artifacts/`
- keep `docs/checkpoint-2026-06-11.md` as the first file to read after cloning

If future Codex resumes work, it should read this file first, then:

1. `docs/state.md`
2. `docs/open-gaps.md`
3. `docs/next-steps.md`
4. `README.md`
