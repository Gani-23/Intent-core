#!/usr/bin/env python3
"""Standalone GitHub Action entrypoint for Intent Guard PR commenting.

Reads local session reports from .intent-guard/reports/ (standalone mode)
or queries the remote LSA API if configured. Formats a concise comment
with an idempotent hidden marker, ensuring subsequent pushes update
the existing comment instead of creating noisy duplicates.
"""
from __future__ import annotations

import json
import os
import re
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPORT_MARKER = "<!-- intent-guard-report-marker -->"
MAX_REPORT_LENGTH = 15000  # Cap maximum embedded length to prevent unbounded payloads
DEFAULT_HTTP_TIMEOUT = 30  # Timeout for GitHub REST API calls

_HTML_TAG_ESCAPE_RE = re.compile(r"</?\s*(details|summary)\b[^>]*>", re.IGNORECASE)


def sanitize_markdown_details(text: str, max_length: int = MAX_REPORT_LENGTH) -> str:
    """Sanitize and limit report text so it cannot break out of <details> or inject raw markdown."""
    text = text.strip()
    if len(text) > max_length:
        text = text[:max_length] + "\n\n... [Report truncated: exceeded 15k characters]"
    text = _HTML_TAG_ESCAPE_RE.sub(
        lambda m: m.group(0).replace("<", "&lt;").replace(">", "&gt;"),
        text,
    )
    return text


def format_pr_comment(reports_content: list[dict[str, str]]) -> str:
    """Format a clean, collapsed PR comment with high-level summary line."""
    if not reports_content:
        return (
            f"{REPORT_MARKER}\n"
            f"### 🛡️ Intent Guard Audit Report\n\n"
            f"✅ **No drift detected this session** — all observed tool executions aligned with declared intent.\n"
        )

    has_unperformed = any(
        r.get("audit_not_performed", False) or "Audit Not Performed" in r.get("content", "")
        for r in reports_content
    )
    total_findings = sum(
        r.get("findings_count") if r.get("findings_count") is not None
        else sum(1 for line in r.get("content", "").splitlines() if line.strip().startswith("- **["))
        for r in reports_content
    )

    if has_unperformed:
        status_emoji = "⚠️"
        finding_str = "**audit not performed** — drift detection engine could not be loaded"
    elif total_findings > 0:
        status_emoji = "⚠️"
        finding_str = f"**{total_findings} finding(s) detected**"
    else:
        status_emoji = "✅"
        finding_str = "clean pass"

    body = [
        f"{REPORT_MARKER}",
        f"### 🛡️ Intent Guard Audit Report",
        f"",
        f"{status_emoji} {finding_str} — see details below before merging.",
        f"",
    ]

    for report in reports_content:
        sess_id = report.get("session_id", "session")
        content = sanitize_markdown_details(report.get("content", ""))
        body.append(f"<details>")
        body.append(f"<summary>📋 Session <code>{sess_id}</code> Report</summary>\n")
        body.append(content)
        body.append(f"\n</details>\n")

    body.append("---")
    body.append("<sub>Audited deterministically by <a href='https://github.com/Gani-23/Intent-core'>intent-guard</a></sub>")
    return "\n".join(body)


def collect_local_reports(report_dir_path: Path) -> list[dict[str, str]]:
    """Scan local directory for session report markdown files (standalone)."""
    reports = []
    if not report_dir_path.exists():
        return reports

    for md_file in sorted(report_dir_path.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        # Count findings lines starting with - **[
        findings_count = sum(1 for line in text.splitlines() if line.strip().startswith("- **["))
        audit_not_performed = "Audit Not Performed" in text
        reports.append({
            "session_id": md_file.stem,
            "findings_count": findings_count,
            "audit_not_performed": audit_not_performed,
            "content": text,
        })
    return reports


def post_or_update_pr_comment(
    repo: str,
    pr_number: int,
    token: str,
    comment_body: str,
    api_base: str = "https://api.github.com",
    timeout: int = DEFAULT_HTTP_TIMEOUT,
) -> tuple[str, int]:
    """Idempotently post or update the PR comment matching REPORT_MARKER."""
    # Normalize token
    raw_token = token.strip()
    if raw_token.startswith("Bearer "):
        raw_token = raw_token[7:].strip()
    elif raw_token.startswith("token "):
        raw_token = raw_token[6:].strip()

    if os.environ.get("INTENT_GUARD_DEBUG") == "1":
        sys.stderr.write(f"Debug: repo={repo}, pr={pr_number}, token_len={len(raw_token)}\n")

    headers = {
        "Authorization": f"Bearer {raw_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "intent-guard-action/1.0",
        "Content-Type": "application/json",
    }

    # 1. Fetch existing comments on PR
    list_url = f"{api_base}/repos/{repo}/issues/{pr_number}/comments"
    req_list = urllib.request.Request(list_url, headers=headers)

    existing_comment_id = None
    try:
        with urllib.request.urlopen(req_list, timeout=timeout) as resp:
            comments = json.loads(resp.read().decode("utf-8"))
            for c in comments:
                if REPORT_MARKER in c.get("body", ""):
                    existing_comment_id = c.get("id")
                    break
    except urllib.error.HTTPError as e:
        if e.code not in (404,):
            sys.stderr.write(f"Warning: Failed to fetch existing comments: {e}\n")
    except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
        sys.stderr.write(f"Warning: Network error or timeout checking comments: {e}\n")

    # 2. Update existing comment or create new comment
    if existing_comment_id:
        update_url = f"{api_base}/repos/{repo}/issues/comments/{existing_comment_id}"
        req_update = urllib.request.Request(
            update_url,
            data=json.dumps({"body": comment_body}).encode("utf-8"),
            headers=headers,
            method="PATCH",
        )
        try:
            with urllib.request.urlopen(req_update, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return "updated", data.get("id", existing_comment_id)
        except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
            raise RuntimeError(f"Network error or timeout updating PR comment: {e}") from e
    else:
        req_post = urllib.request.Request(
            list_url,
            data=json.dumps({"body": comment_body}).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req_post, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return "created", data.get("id", 0)
        except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
            raise RuntimeError(f"Network error or timeout creating PR comment: {e}") from e


def resolve_pr_number() -> int | None:
    """Resolve PR number from explicit PR_NUMBER env var or GitHub Event JSON fallback.

    Returns:
        int PR number if in a pull request context, or None if non-PR trigger event.
    """
    raw_pr = os.environ.get("PR_NUMBER", "").strip()
    if raw_pr and raw_pr.isdigit():
        return int(raw_pr)

    event_path_str = os.environ.get("GITHUB_EVENT_PATH")
    if event_path_str:
        event_path = Path(event_path_str)
        if event_path.exists():
            try:
                event_data = json.loads(event_path.read_text(encoding="utf-8"))
                # Check for pull_request object in event JSON
                pr_obj = event_data.get("pull_request")
                if isinstance(pr_obj, dict) and pr_obj.get("number"):
                    return int(pr_obj["number"])
                # Also check issue object if triggered on issue_comment
                issue_obj = event_data.get("issue")
                if isinstance(issue_obj, dict) and issue_obj.get("pull_request") and issue_obj.get("number"):
                    return int(issue_obj["number"])
            except Exception as e:
                sys.stderr.write(f"Warning: Failed to parse GITHUB_EVENT_PATH ({event_path}): {e}\n")

    return None


def fetch_pr_context_and_files(
    repo: str,
    pr_number: int,
    token: str,
    api_base: str = "https://api.github.com",
    timeout: int = DEFAULT_HTTP_TIMEOUT,
) -> tuple[str, str, list[dict[str, str]]]:
    """Fetch PR title, body, and list of changed files from GitHub REST API."""
    raw_token = token.strip()
    if raw_token.startswith("Bearer "):
        raw_token = raw_token[7:].strip()
    elif raw_token.startswith("token "):
        raw_token = raw_token[6:].strip()

    headers = {
        "Authorization": f"Bearer {raw_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "intent-guard-action/1.0",
    }

    # 1. PR Details
    title, body = "", ""
    try:
        pr_url = f"{api_base}/repos/{repo}/pulls/{pr_number}"
        req = urllib.request.Request(pr_url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            title = data.get("title", "")
            body = data.get("body", "") or ""
    except Exception as e:
        sys.stderr.write(f"Warning: Could not fetch PR #{pr_number} metadata: {e}\n")

    # 2. PR Files
    files: list[dict[str, str]] = []
    try:
        files_url = f"{api_base}/repos/{repo}/pulls/{pr_number}/files?per_page=100"
        req = urllib.request.Request(files_url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            files_data = json.loads(resp.read().decode("utf-8"))
            for f in files_data:
                files.append({
                    "filename": f.get("filename", ""),
                    "status": f.get("status", "modified"),
                    "patch": f.get("patch", ""),
                })
    except Exception as e:
        sys.stderr.write(f"Warning: Could not fetch PR #{pr_number} files: {e}\n")

    return title, body, files


def dynamic_pr_audit(
    repo: str,
    pr_number: int,
    title: str,
    body: str,
    files: list[dict[str, str]],
    report_dir: Path,
) -> Path | None:
    """Run real Intent Guard drift engine against PR git diff & intent description."""
    if not files:
        return None

    task_description = f"{title}\n{body}".strip()
    if not task_description:
        task_description = "Unspecified Pull Request modification"

    # Attempt to import core drift engine from action repository
    action_root = Path(os.environ.get("ACTION_PATH", Path(__file__).resolve().parent.parent))
    if str(action_root) not in sys.path:
        sys.path.insert(0, str(action_root))

    alerts: list[dict[str, str]] = []
    check_ran = False

    try:
        from lsa.drift.diff_audit import StaticDiffAuditor
        check_ran = True
    except ImportError as e:
        check_ran = False
        sys.stderr.write(f"Warning: Failed to import StaticDiffAuditor: {e}\n")

    if check_ran:
        auditor = StaticDiffAuditor()
        findings = auditor.audit_pr(title, body, files)
        for finding in findings:
            alerts.append({
                "target": finding.target,
                "severity": finding.severity,
                "reason": finding.reason,
            })

    # Generate genuine session report markdown
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"pr-{pr_number}-intent-audit.md"

    report_lines = [
        f"# Intent Guard PR Drift Audit (PR #{pr_number})",
        "",
        f"## Declared Intent (From PR Title & Description)",
        f"```text",
        f"{task_description[:500]}",
        f"```",
        "",
        f"## Files Modified in Pull Request ({len(files)} files)",
    ]
    for f in files[:20]:
        st = f.get("status", "modified")
        report_lines.append(f"- `{f['filename']}` ({st})")
    if len(files) > 20:
        report_lines.append(f"- ... and {len(files) - 20} more files")

    report_lines.append("")
    report_lines.append("## Dynamic Audit Findings")
    if not check_ran:
        report_lines.append(
            "⚠️ **Audit Not Performed**: the drift detection engine could not be loaded in this environment. "
            "No conclusion can be drawn about this PR's alignment with its stated intent."
        )
    elif alerts:
        for alert in alerts:
            sev_badge = alert['severity'].upper()
            report_lines.append(f"- **[{sev_badge}]** `{alert['target']}`: {alert['reason']}")
        report_lines.append("")
        report_lines.append("## Remediation Recommendation")
        report_lines.append("Review the flagged files above to ensure they align with the declared PR intent before merging.")
    else:
        report_lines.append("✅ **Clean Pass**: All modified files and diff patterns strictly adhere to declared intent and security boundaries.")

    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    return report_path


def main() -> int:
    report_dir = Path(os.environ.get("REPORT_DIR", ".intent-guard/reports"))
    reports = collect_local_reports(report_dir)

    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    pr_num = resolve_pr_number()
    auto_audit = os.environ.get("AUTO_AUDIT_PR", "true").lower() in ("true", "1", "yes")

    # If no pre-existing session reports exist, dynamically audit PR diff
    if not reports and auto_audit and token and repo and pr_num is not None:
        print(f"Intent Guard: No pre-existing session reports found. Dynamically auditing PR #{pr_num} git diff...")
        title, body, files = fetch_pr_context_and_files(repo, pr_num, token)
        gen_path = dynamic_pr_audit(repo, pr_num, title, body, files, report_dir)
        if gen_path and gen_path.exists():
            reports = collect_local_reports(report_dir)

    comment = format_pr_comment(reports)
    total_findings = sum(r.get("findings_count", 1) for r in reports) if reports else 0

    # 1. Always append report to GitHub Actions Job Step Summary
    step_summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary_path:
        try:
            with open(step_summary_path, "a", encoding="utf-8") as f:
                f.write(f"\n{comment}\n")
        except Exception as e:
            sys.stderr.write(f"Warning: Failed to write to GITHUB_STEP_SUMMARY: {e}\n")

    # 2. Set action output parameters
    github_output_path = os.environ.get("GITHUB_OUTPUT")
    if github_output_path:
        try:
            with open(github_output_path, "a", encoding="utf-8") as f:
                f.write(f"findings_count={total_findings}\n")
                f.write(f"reports_found={len(reports)}\n")
        except Exception as e:
            sys.stderr.write(f"Warning: Failed to write to GITHUB_OUTPUT: {e}\n")

    # 3. If running in GitHub Actions with PR context, post/update PR sticky comment
    if token and repo and pr_num is not None:
        try:
            action, cid = post_or_update_pr_comment(repo, pr_num, token, comment)
            print(f"Successfully {action} Intent Guard comment #{cid} on {repo}#{pr_num}")
        except Exception as e:
            sys.stderr.write(f"Error posting comment to GitHub: {e}\n")
            return 1
    else:
        if token and repo and pr_num is None:
            print("Intent Guard: non-pull_request trigger event (e.g. push or manual run). No PR to comment on.")
        print("Intent Guard PR Comment (Dry-Run / Local Preview):")
        print(comment)

    return 0


if __name__ == "__main__":
    sys.exit(main())
