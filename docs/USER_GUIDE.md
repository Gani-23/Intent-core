# Intent Guard — User Guide & Manual

Welcome to **Intent Guard**! This guide walks you through everything you need to know to use Intent Guard—whether you are running AI coding agents locally in your terminal or running autonomous agent pipelines in GitHub Actions CI/CD.

---

## 1. What Is Intent Guard? (ELI5)

When you ask an AI coding assistant (like Claude Code, Cursor, or an autonomous PR bot):
> *"Check the database configuration. Read-only, do not modify or delete anything."*

Existing security tools and linters only check if the code syntax is valid or if there is a known vulnerability. They have **no idea what you actually asked**.

If the agent decides to run:
```sql
UPDATE users SET verified=true WHERE id=445;
```
Standard tools won't stop it because `UPDATE` is valid SQL. But **it directly violates your instructions**.

**Intent Guard bridges this gap.** It acts as an independent safety auditor:
1. It records **what you asked** at the start of a session and cryptographically signs it.
2. It monitors **what the agent actually does** (files edited, shell commands run, network hosts contacted).
3. It performs **two analysis passes**:
   - **Pass 1 (Instant Regex)**: Blocks known destructive actions (`rm -rf /`, `DROP TABLE`, force-pushing to git).
   - **Pass 2 (Semantic Review)**: Analyzes the whole session to catch subtle contradictions (like executing database modifications during an explicit read-only audit).
4. It reports findings directly onto your **GitHub Pull Requests** or inside your terminal.

---

## 2. Using Intent Guard in GitHub Actions (The 3-Minute Setup)

If you are using Intent Guard from the **GitHub Marketplace**, this is the fastest way to get started.

### Step 1: Add the Workflow File
In your repository, create `.github/workflows/intent-guard.yml`:

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
          github_token: ${{ github.token }}
          report_dir: ".intent-guard/reports"
```

> [!TIP]
> **No secret configuration required**: `${{ github.token }}` is a built-in variable automatically provided by GitHub Actions for every run. You do **not** need to create a secret in your repository settings (if you attempt to create a secret named `GITHUB_TOKEN`, GitHub will reject it with `"Secret names must not start with GITHUB_"`).

### Step 2: How It Works on Pull Requests
Whenever an agent (or human) opens a Pull Request or pushes new code:
1. The GitHub Action scans `.intent-guard/reports/` for audit findings.
2. It automatically formats and posts an audit summary comment on the Pull Request:

```markdown
<!-- intent-guard-report-marker -->
### 🛡️ Intent Guard Audit Report

⚠️ **1 finding(s) detected** — see details below before merging.

<details>
<summary>📋 Session <code>session_2026_09</code> Report</summary>

# Drift report for session: session_2026_09

## Summary
Task specified explicit constraint: "read-only audit, do not modify records",
but the agent executed: `UPDATE users SET verified=true WHERE id=445`.

## Risk
CRITICAL

## Recommended Immediate Action
Pause and verify whether this modification was intended before merging.

</details>

---
<sub>Audited deterministically by intent-guard</sub>
```

### Step 3: Noise-Free Updates (Idempotency)
If you push another commit to the same PR, Intent Guard **does not post duplicate comments**. It finds the previous comment using a hidden marker and **updates it in-place**, keeping your PR review thread clean.

### Step 4 (Optional): Enforce a Quality Gate
Want to block merging if a critical violation occurred? Add this step after the commenter:

```yaml
      - name: Fail CI on Critical Drift
        run: |
          python3 -c "
          from pathlib import Path
          import sys
          reports = list(Path('.intent-guard/reports').glob('*.md'))
          critical = any('CRITICAL' in r.read_text(encoding='utf-8') for r in reports)
          if critical:
              print('❌ PR Blocked: Critical intent drift detected!')
              sys.exit(1)
          print('✅ PR Quality Gate Passed: No critical drift.')
          "
```

---

## 3. Using Intent Guard with Claude Code CLI (Local Development)

You can run Intent Guard locally while using Claude Code.

### Step 1: Clone and Register the Plugin
Clone this repository to your machine:
```bash
git clone https://github.com/Gani-23/Intent-core.git intent-guard
cd intent-guard
```

Point Claude Code to the plugin directory:
```bash
export CLAUDE_PLUGIN_ROOT="$(pwd)"
```

### Step 2: Choose Your Execution Posture

#### Posture A: Individual Developer Mode (Default: Fail-Open)
```bash
export INTENT_GUARD_MODE=observe
```
- **Behavior**: Silently observes commands and file edits.
- Never interrupts your workflow or stops the agent.
- Generates a full markdown report in `.intent-guard/reports/` when the session ends.
- If anything fails internally, it fails open so you can keep coding without friction.

#### Posture B: Enterprise Strict Mode (Pre-Tool Blocking)
```bash
export INTENT_GUARD_MODE=strict
export INTENT_GUARD_FAIL_CLOSED=true
```
- **Behavior**: Intercepts shell commands **before they execute**.
- If the agent attempts `rm -rf /`, `DROP TABLE`, `git push --force`, or violates an explicit negative constraint in your prompt, Intent Guard **aborts the command immediately**:
  ```text
  [intent-guard strict] Blocked 'database table destruction' pattern before execution.
  To allow, disable strict mode or add this command to your session scope explicitly.
  ```

### Step 3: Run Claude Code Normally
Talk to Claude Code as you usually do:
```bash
claude "Refactor user authentication in src/auth.py. Do not modify database schemas."
```

When the session ends, Intent Guard will notify you in your terminal:
```json
{"systemMessage": "intent-guard flagged 0 actions this session (highest severity: none). Full report: .intent-guard/reports/sess_123.md"}
```

---

## 4. Multi-Provider AI Cascade (Zero-Cost & Offline Friendly)

Intent Guard's semantic review pass uses a resilient multi-provider cascade so you never get stuck:

1. **Anthropic (`ANTHROPIC_API_KEY`)**: Uses Claude 3.5 Sonnet if available.
2. **OpenAI (`OPENAI_API_KEY`)**: Fails over to `gpt-4o-mini`.
3. **Gemini (`GEMINI_API_KEY` or `GOOGLE_API_KEY`)**: Fails over to `gemini-2.5-flash`.
4. **Antigravity Local Bridge**: Runs 100% locally via Apple Silicon / Mac Mini with **zero cloud API tokens**.
5. **Deterministic Failsafe**: If all API keys are absent and you are offline, it uses pure standard library regex and AST checking. **It will never crash or require external pip packages.**

---

## 5. Configuration Reference

### Environment Variables

| Variable | Values | Default | Description |
| :--- | :--- | :--- | :--- |
| `INTENT_GUARD_MODE` | `observe` \| `strict` | `observe` | `observe` records telemetry only; `strict` blocks dangerous shell commands before execution. |
| `INTENT_GUARD_FAIL_CLOSED` | `true` \| `false` | `false` | When `true`, halts tool execution if manifest signatures cannot be verified. Recommended for CI. |
| `INTENT_GUARD_RETAIN_EVENTS` | `true` \| `false` | `false` | When `true`, archives raw event traces in `.intent-guard/archive/` instead of deleting them. |
| `LSA_SIEM_WEBHOOK_URL` | URL string | None | Optional endpoint to stream real-time JSON security alerts to your SIEM (e.g. Datadog, Splunk). |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | None | API key for Anthropic Claude semantic review pass. |
| `OPENAI_API_KEY` | `sk-...` | None | Fallback API key for OpenAI review pass. |
| `GEMINI_API_KEY` | `AIza...` | None | Fallback API key for Google Gemini review pass. |

### GitHub Action Inputs (`action.yml`)

| Input | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `github_token` | **Yes** | N/A | Automatically provided by GitHub (`${{ github.token }}`). Do **not** create a secret named `GITHUB_TOKEN`. |
| `pr_number` | No | Auto-detected | PR number (defaults to `github.event.pull_request.number`). |
| `report_dir` | No | `.intent-guard/reports` | Directory where markdown reports are stored. |
| `api_url` | No | `""` | Optional central LSA API URL for team telemetry. |
| `api_key` | No | `""` | Optional API key for remote LSA telemetry. |

---

## 6. Frequently Asked Questions (FAQ)

#### Q: Why does GitHub say "Secret names must not start with GITHUB_"?
**A:** Because `GITHUB_TOKEN` is an internal, built-in token provided automatically by GitHub Actions! GitHub reserves the `GITHUB_` prefix so users don't accidentally overwrite system variables. You **never** need to manually create a secret named `GITHUB_TOKEN` in Repository Settings. Just use `${{ github.token }}` in your workflow YAML, and GitHub handles it automatically.

#### Q: Does Intent Guard slow down my coding agent?
**A:** No. Pass 1 (regex matching) takes less than 1 millisecond. Pass 2 (semantic review) runs once when the session ends (`Stop` hook) or inside your GitHub Actions CI runner.

#### Q: Does Intent Guard require third-party dependencies?
**A:** No. The core hooks, manifest signers, and GitHub Action commenter are written using pure Python standard library (`json`, `urllib`, `hmac`, `re`). There are zero external packages to install.

#### Q: What if an agent tries to modify its own scope?
**A:** At prompt submission, Intent Guard calculates an HMAC-SHA256 signature using a machine-local key (`.intent-guard/machine.key`). If an agent modifies its prompt or scope file mid-session, the signature check fails and triggers an integrity alert.

#### Q: Can I run this in private corporate GitHub repositories?
**A:** Yes. The default `${{ github.token }}` provided by GitHub Actions has all the permissions needed. No data leaves your GitHub runner unless you explicitly configure an external webhook.
