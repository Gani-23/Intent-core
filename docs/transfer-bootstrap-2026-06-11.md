# Transfer Bootstrap

Date: 2026-06-11

Use this file on the new machine as the first practical setup guide after cloning the repo.

## 1) What This Repo Is

Living Systems Auditor is a FastAPI backend plus a separate Vite + React frontend.

Main product areas:

- command center
- target registry and proof tooling
- runtime reviews
- incidents and alerts
- proof bundles
- admin access
- admin workspace
- admin secrets
- onboarding and launch guide

## 2) What Not To Commit

Keep these out of Git:

- `.env.local`
- `.venv/`
- `dashboard/node_modules/`
- `dashboard/dist/`
- `dashboard/.vite/`
- `frontend/node_modules/`
- `frontend/dist/`
- `data/` runtime outputs
- `artifacts/`

The repo `.gitignore` already covers the important generated paths.

## 3) Minimum Prerequisites

Install:

- Python 3.12+ or 3.13+
- Node 20+ if you want the frontend
- `npm`
- `git`

Optional but useful:

- `jq`
- `curl`

## 4) Fresh Clone Setup

```bash
cd /path/to/clone
```

If using the existing repo layout:

```bash
cd /Users/gani/Desktop/Intent-drive/living-systems-auditor
```

## 5) Backend Setup

Create the virtual environment if needed:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

If extras are needed for your run mode, install them from the project docs or the relevant scripts.

## 6) Frontend Setup

```bash
cd dashboard
npm install
```

## 7) Environment File

Create `.env.local` in the repo root.

Recommended baseline for local use:

```bash
LSA_ENABLE_REMEDIATION_MODEL=1
LSA_REMEDIATION_PROVIDER=openai-compatible
LSA_REMEDIATION_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LSA_REMEDIATION_MODEL=gemini-2.5-flash
LSA_REMEDIATION_API_KEY=replace_me
LSA_OAUTH_ENABLED=1
LSA_OAUTH_VALIDATION_URL=https://oauth4-0.onrender.com/api/users/licenses/validate
```

Optional production-style variables:

```bash
LSA_API_KEY=replace_me
LSA_API_ALLOWED_ORIGINS=http://127.0.0.1:1234
LSA_API_TRUSTED_HOSTS=127.0.0.1,localhost
LSA_API_SECURITY_HEADERS_ENABLED=1
LSA_ENABLE_POSTGRES_RUNTIME=0
LSA_DATABASE_URL=sqlite:////Users/gani/Desktop/Intent-drive/living-systems-auditor/data/control_plane.db
```

For Postgres runs, set:

```bash
LSA_ENABLE_POSTGRES_RUNTIME=1
LSA_POSTGRES_RUNTIME_DATABASE_URL=postgresql://...
LSA_DATABASE_URL=postgresql://...
```

## 8) Start Backend

Local script:

```bash
bash scripts/run_local_backend.sh
```

Split-stack launcher:

```bash
bash scripts/run_local_stack.sh --testing
```

Manual uvicorn:

```bash
./.venv/bin/python -m uvicorn lsa.api.main:app --host 127.0.0.1 --port 3614
```

## 9) Start Frontend

```bash
cd dashboard
npm run dev -- --host 127.0.0.1 --port 1234
```

## 10) Open The App

- Backend health: [http://127.0.0.1:3614/health](http://127.0.0.1:3614/health)
- Frontend home: [http://127.0.0.1:1234/](http://127.0.0.1:1234/)
- Command center: [http://127.0.0.1:1234/command](http://127.0.0.1:1234/command)
- Targets: [http://127.0.0.1:1234/targets](http://127.0.0.1:1234/targets)
- Login: [http://127.0.0.1:1234/login](http://127.0.0.1:1234/login)
- Admin access: [http://127.0.0.1:1234/admin/access](http://127.0.0.1:1234/admin/access)
- Workspace: [http://127.0.0.1:1234/admin/workspace](http://127.0.0.1:1234/admin/workspace)
- Secrets: [http://127.0.0.1:1234/admin/secrets](http://127.0.0.1:1234/admin/secrets)

## 11) OAuth Login

The hosted OAuth app is:

- [https://oauth4-0.onrender.com](https://oauth4-0.onrender.com)

Login flow:

1. open `/login`
2. sign in with the OAuth user
3. admin users can open access/workspace/secrets surfaces
4. scopes are inherited from the OAuth token

## 12) Target Profiles

Target profiles live in the UI and can also be backed by a file:

```bash
LSA_WORKLOAD_TARGET_PROFILES_PATH=/path/to/workload_target_profiles.json
```

Supported target fields include:

- approved/drift base URLs
- validation URLs
- proof URLs
- HTTP methods
- headers
- expected statuses
- timeout
- organization/team/project/environment metadata

Headers can use:

- `env:NAME`
- `secret:alias`

## 13) Secret Aliases

Secret aliases are env-backed references.

Rules:

- alias format: lowercase `snake_case`
- env var format: uppercase `SNAKE_CASE`

Example:

```json
{
  "alias": "prod_api_token",
  "env_var_name": "PROD_API_TOKEN",
  "description": "Bearer token for production API",
  "usage_scope": "targets"
}
```

The alias registry file is:

```bash
data/secret_aliases.json
```

## 14) How To Verify It Works

Backend quick check:

```bash
curl -sS http://127.0.0.1:3614/health | jq
```

Useful backend proof commands:

```bash
./.venv/bin/python -m lsa.cli.main control-plane-trust-score
./.venv/bin/python -m lsa.cli.main control-plane-incident-narrative
./.venv/bin/python -m lsa.cli.main control-plane-live-workload-target-validation
./.venv/bin/python -m lsa.cli.main run-control-plane-operational-validation --by gani --expected-backend sqlite --reason "bootstrap check"
./.venv/bin/python -m lsa.cli.main run-control-plane-soak-validation --by gani --expected-backend sqlite --reason "bootstrap check" --iterations 1 --pause-seconds 0
```

Frontend quick check:

```bash
cd dashboard
npm run build
```

## 15) What To Do First After Opening On New Machine

1. read this file
2. read `docs/checkpoint-2026-06-11.md`
3. start backend
4. start frontend
5. open `/health`, `/command`, and `/targets`
6. confirm OAuth login works
7. confirm a target profile can validate

## 16) If Disk Starts Growing Again

The main growth source was backup archives in:

```bash
data/control_plane_backups/
```

Keep only a small rolling window of backups.

Also watch:

- `data/control_plane.db-wal`
- `data/observability_exports/`
- `data/live_workload_proof_exports/`
- `data/reports/`
- `data/intent_graphs/`
- `data/soak_runs/`

## 17) Recommended Next Work On The New Machine

1. secure secret storage
2. deeper org/team/project isolation across all records
3. authz/security review
4. stronger evidence retention/pruning
5. external proof breadth
6. final frontend polish
