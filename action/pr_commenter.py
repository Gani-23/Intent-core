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

    total_findings = sum(r.get("findings_count", 1) for r in reports_content)
    finding_str = f"**{total_findings} finding(s) detected**" if total_findings > 0 else "clean pass"
    status_emoji = "⚠️" if total_findings > 0 else "✅"

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
        reports.append({
            "session_id": md_file.stem,
            "findings_count": max(1, findings_count),
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
    auth_header = token if token.startswith(("Bearer ", "token ")) else f"token {token}"
    headers = {
        "Authorization": auth_header,
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


def main() -> int:
    report_dir = Path(os.environ.get("REPORT_DIR", ".intent-guard/reports"))
    reports = collect_local_reports(report_dir)
    comment = format_pr_comment(reports)

    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    pr_num = resolve_pr_number()

    # If running in GitHub Actions with PR context
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
