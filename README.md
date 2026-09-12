<p align="center">
  <img src="assets/icon.png" alt="Intent Guard Logo" width="160" height="160" style="border-radius: 24px;" />
</p>

# 🛡️ Intent Guard

> **Runtime Semantic Drift Auditor & PR Safety Gate for AI Coding Agents**

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-102%20passed-brightgreen.svg)](tests/)
[![Dependencies](https://img.shields.io/badge/dependencies-zero%20external%20pip-success.svg)](action.yml)
[![Marketplace](https://img.shields.io/badge/marketplace-Intent%20Guard%20PR%20Auditor-blueviolet.svg)](https://github.com/marketplace/actions/intent-guard-pr-auditor)

**Most agent-safety tools check who an AI coding agent is or what it's allowed to touch. This checks whether what it actually did still matches what you asked — which is the only thing that would have caught Replit deleting a production database during a code freeze.**

Intent Guard runs as a lightweight GitHub Action on Pull Requests or as a local hook for AI coding agents (Claude Code, Cursor, Copilot workspaces, OpenCode). It verifies that an agent's proposed changes and tool executions strictly adhere to declared intent, catching unauthorized mutations, destructive commands, and semantic drift before they hit production.

---

## ⚡ Quick Start (2-Minute Setup)

### Option 1: GitHub Actions (Pull Request Auditor)

Add `.github/workflows/intent-guard.yml` to your repo:

```yaml
name: "Intent Guard PR Audit"
on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: Gani-23/Intent-core@main
        with:
          github_token: ${{ secrets.GH_TOKEN || github.token }}
```

> **Token Tip**: You can pass a custom Personal Access Token named `GH_TOKEN` (`${{ secrets.GH_TOKEN }}` in repository secrets), or omit it to automatically use the built-in `${{ github.token }}`.

Whenever a Pull Request is opened, Intent Guard automatically posts and idempotently updates a clean audit report directly on the PR conversation thread.

### Option 2: Claude Code CLI Plugin (Local Development)

```bash
# 1. Point Claude Code to the plugin directory
export CLAUDE_PLUGIN_ROOT="$(pwd)"

# 2. Run Claude Code normally — Intent Guard automatically audits prompts & tools
claude "Refactor auth middleware in src/auth.py without touching database models"
```

👉 **Need a step-by-step walkthrough?** Check out the comprehensive **[User Guide & Manual (docs/USER_GUIDE.md)](docs/USER_GUIDE.md)** or the **[GitHub Actions Integration Guide (docs/github-actions.md)](docs/github-actions.md)**.

---

## Why this exists

Existing agent-safety tooling checks identity/credentials (who the agent
is), code content (does the code look vulnerable), or output quality (was
the reasoning good). None of them ask the one question that actually
mattered in the real 2026 incidents this is modeled on — Replit deleting a
production DB during a code freeze, a Cursor agent deleting a database via
an over-scoped token in nine seconds, a routine-looking Prisma command
wiping tables via a shadow-database reset: **did the whole set of things the
agent did still match what was asked, in aggregate** — not what it was
credentialed to touch, not whether the command matched a blocklist pattern.

## Detection architecture (two passes)

1. **Regex pass** (`mutation_rules.py`, `MutationComparator`) — fast, free, always on. Catches known-bad syntax (`rm -rf`, `DROP TABLE`, `--force` push) and direct contradictions of something the human explicitly said not to do. Zero API cost, zero latency.
2. **Semantic pass** (`semantic_review.py`, `SemanticSessionReviewer`) — reads the session (task description + every action taken) and judges fit as a human reviewer would, catching things no keyword list ever will. Example proven in `examples/demo_pocketos_scenario.py`: a task says "read-only audit, do not modify records" and the session runs `UPDATE users SET verified=true WHERE id=445` — zero regex alerts, because nothing about `UPDATE ... WHERE` looks dangerous.

Pass 2 features a robust **multi-provider failsafe cascade**:
- **Anthropic**: Uses `ANTHROPIC_API_KEY` (Claude).
- **OpenAI**: Fails over to `OPENAI_API_KEY` (e.g. `gpt-4o-mini`).
- **Gemini**: Fails over to `GEMINI_API_KEY` or `GOOGLE_API_KEY` (`gemini-2.5-flash`).
- **Antigravity**: Local bridge via `agentapi new-conversation` on Mac Mini/Apple Silicon — runs 100% locally with zero cloud API keys needed (verified in ~2.5s).
- **Deterministic Failsafe**: If all tokens are absent and all network providers fail, evaluates explicit task prohibitions against mutation statements (`UPDATE`, `INSERT`, `DELETE`) without crashing. Zero external pip packages (pure stdlib).

## What's actually proven vs. what's a first pass

**Proven, tested end-to-end in this sandbox** (see `examples/`):
- The comparator correctly flags a destructive, task-contradicting action
  (recreates the Prisma/PocketOS incident shape) and does *not* flag a
  benign, in-scope edit — verified by running it, not just reading it.
- The three hook scripts run correctly against simulated Claude Code stdin
  end-to-end: capture → compare → report → rotate.
- Every file compiles clean. Zero external dependencies — pure stdlib, so
  there's nothing to `pip install` for the hooks themselves.

**A first pass, not a finished product:**
- `CONSTRAINT_PHRASES` and `DESTRUCTIVE_PATTERNS` in `mutation_rules.py` are
  a starting set of regexes, not a validated list. Expect false negatives
  (patterns not yet covered) and occasional false positives — the first
  version already had one (an in-scope `.env` edit flagged as critical; see
  git history in the conversation this was built in for how it was caught
  and fixed). Treat every alert as a hypothesis to sanity-check, not a
  verdict, until this has run against real sessions.
- The field names in `hooks/*.py` (`session_id`, `prompt`, `tool_name`,
  `tool_input`) were verified against the actual Claude Code v2.1.259
  binary (`strings` on the compiled release, not just the docs site) — all
  four appear exactly as used here. **Still unverified:** the exact JSON
  envelope shape (nesting) and real runtime behavior, which need an
  authenticated session on real hardware to confirm. Known gap found during
  this verification: `tool_response` is a real field this doesn't read yet
  — right now a Bash command is logged as having run, not whether it
  succeeded, which matters for severity.
- No blocking yet — hooks only observe and report after the fact (exit code
  0 always). Turning flagged actions into an actual `PreToolUse` deny is a
  natural v2, deliberately not v1: shipping observe-only first means
  adopting this costs nothing and can't break anyone's existing flow.
- The network-destination side of the original engine (`trace_parser.py`,
  `ebpf_observer.py`, `function_resolution.py`, `destination_resolution.py`)
  is carried over but not wired into the hooks path. It's a legitimate
  second signal (catches an agent quietly calling an undeclared host) for a
  later "deep verification" tier — not required for the MVP.

## Setup

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # optional — falls back to multi-provider cascade
                                        # (OpenAI, Gemini, Antigravity, or deterministic)
python3 examples/demo_pocketos_scenario.py   # run this first
```

To install as a Claude Code plugin, point `CLAUDE_PLUGIN_ROOT` at this directory and register `hooks/hooks.json` per Claude Code plugin documentation.

> [!WARNING]
> **Runtime Verification Status**:
> The hook scripts (`capture_scope.py`, `pre_tool_check.py`, `capture_event.py`, `session_report.py`) have been rigorously tested and verified end-to-end using simulated stdin JSON payloads matching Claude Code's binary schema. However, integration inside an active, interactive Claude Code live session remains unverified pending an authenticated test account in this environment.

## Deployment & Enforcement Policies (Fail-Open vs. Fail-Closed)

`intent-guard` supports two execution postures:

1. **Individual Developer Mode (Default: Fail-Open)**:
   - `INTENT_GUARD_MODE=observe` (default): Emits telemetry and writes reports at session end without blocking agent turn flow.
   - If an internal error occurs (e.g. malformed JSON, unreadable state file), `intent-guard` safely fails open to avoid disrupting developer productivity.

2. **Enterprise Strict Mode (Fail-Closed Option)**:
   - `INTENT_GUARD_MODE=strict`: Enables `PreToolUse` blocking for high-risk destructive actions (`rm -rf /`, `DROP TABLE`, force pushes, etc.) and enforces scope manifest integrity.
   - `INTENT_GUARD_FAIL_CLOSED=true`: Configures the pre-tool gate to **fail closed**. If scope signatures are missing, keys cannot be read, or verification errors occur, the tool execution is halted. This is recommended for regulated enterprise and CI environments.
    - `INTENT_GUARD_RETAIN_EVENTS=true`: Retains raw session traces, scopes, and verification signatures in `.intent-guard/archive/` instead of deleting them at session end, meeting SOC2/compliance audit trail requirements.

## GitHub Actions & PR Auditor (Marketplace)

`intent-guard` includes a standalone GitHub Action (`action.yml`) that reads generated session reports and automatically posts/updates an idempotent audit report directly onto GitHub Pull Requests.

### Quickstart Workflow

Add `.github/workflows/intent-guard.yml` to your repository:

```yaml
name: "Intent Guard PR Audit"

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Audit & Comment on PR
        uses: Gani-23/Intent-core@main # or release tag e.g. @v0.1.0
        with:
          github_token: ${{ secrets.GH_TOKEN || github.token }}
          report_dir: ".intent-guard/reports"
```

### Action Inputs

| Input | Description | Required | Default |
| :--- | :--- | :--- | :--- |
| `github_token` | Personal access token (`${{ secrets.GH_TOKEN }}`) or built-in token (`${{ github.token }}`). | No | `${{ github.token }}` |
| `pr_number` | PR number (auto-detected from event context if omitted) | No | `github.event.pull_request.number` |
| `report_dir` | Directory containing session report markdown files | No | `.intent-guard/reports` |
| `api_url` | Optional LSA central API URL for remote organization telemetry | No | `""` |
| `api_key` | Optional LSA API Key | No | `""` |

For advanced CI setups (running Claude Code headlessly in CI, blocking merges on critical drift, and compliance archiving), see the full guide in [docs/github-actions.md](docs/github-actions.md) and workflow templates in [examples/github-actions/](examples/github-actions/).

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
