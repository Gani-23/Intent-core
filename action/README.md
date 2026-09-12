# Intent Guard GitHub Action (PR Auditor)

Automated PR commenting and quality gate action for [intent-guard](https://github.com/Gani-23/Intent-core).

This action inspects execution drift reports generated during AI coding agent sessions (e.g. Claude Code, Copilot, SWE-bench runners, or custom agents) and posts an idempotent, structured audit report directly onto the GitHub Pull Request.

---

## Features

- 🛡️ **Idempotent PR Commenting**: Uses hidden marker comments (`<!-- intent-guard-report-marker -->`) to update existing comments on subsequent pushes instead of polluting the PR thread.
- 📋 **Collapsible Reports**: Keeps PR conversations clean by summarizing overall findings with expandable `<details>` blocks per session.
- ⚡ **Zero External Dependencies**: Pure Python standard library — runs natively on any GitHub-hosted runner (`ubuntu-latest`, `macos-latest`, `windows-latest`) in under 2 seconds.
- 🏢 **Centralized Telemetry (Optional)**: Can sync audit findings to a central Living Systems Auditor (LSA) API endpoint for organization-wide compliance logging.

---

## Action Inputs

| Input | Description | Required | Default |
| :--- | :--- | :--- | :--- |
| `github_token` | Custom Personal Access Token (`${{ secrets.GH_TOKEN }}`) or built-in token (`${{ github.token }}`). | No | `${{ github.token }}` |
| `pr_number` | Target PR number (auto-detected from event payload if omitted) | No | `github.event.pull_request.number` |
| `report_dir` | Directory containing generated session report markdown files | No | `.intent-guard/reports` |
| `api_url` | Optional LSA central API URL for remote organization telemetry | No | `""` |
| `api_key` | Optional LSA API key for central telemetry authentication | No | `""` |

---

## Quickstart

Add the following step to your `.github/workflows/pr-audit.yml`:

```yaml
name: Intent Guard Audit

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write

jobs:
  audit-pr:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Post Intent Drift Report to PR
        uses: Gani-23/Intent-core@main # or release tag e.g. @v0.1.0
        with:
          github_token: ${{ secrets.GH_TOKEN || github.token }}
          report_dir: ".intent-guard/reports"
```

---

## Permissions Required

Your GitHub Actions job requires write permission on pull requests to leave comments:

```yaml
permissions:
  contents: read
  pull-requests: write
```

---

## Local Dry-Run Testing

You can test the commenter script locally before running in CI:

```bash
# Run against local reports directory
python3 action/pr_commenter.py
```

If `GITHUB_TOKEN` and `GITHUB_REPOSITORY` are not set, it performs a dry-run preview and prints the exact formatted comment markdown to stdout.
