#!/usr/bin/env python3
"""PostToolUse hook.

Reads the tool-call JSON Claude Code sends on stdin, classifies it into an
ObservedEvent with execution outcome, and appends ONE line of JSON to a per-session trace file.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

STATE_DIR = Path(".intent-guard")

MUTATION_TOOLS = {"Write", "Edit", "MultiEdit", "Bash", "NotebookEdit"}


def classify(tool_name: str, tool_input: dict) -> tuple[str, str, str] | None:
    """Returns (target, command, function-ish label) or None to skip."""
    if tool_name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        target = str(tool_input.get("file_path", tool_input.get("notebook_path", "")))
        return target, "", tool_name
    if tool_name == "Bash":
        command = str(tool_input.get("command", ""))
        return command, command, tool_name
    if tool_name.startswith("mcp__"):
        target = json.dumps(tool_input)[:200]
        return target, "", tool_name
    return None


def parse_tool_response(response: object) -> tuple[bool, int | None, str]:
    """Extracts (success, exit_code, output_snippet) from tool_response."""
    if response is None:
        return True, 0, ""
    if isinstance(response, dict):
        exit_code = response.get("exit_code", response.get("exitCode", response.get("status")))
        is_error = bool(response.get("is_error", response.get("error", False)))
        if exit_code is not None and exit_code != 0:
            is_error = True
        snippet = str(response.get("stderr") or response.get("stdout") or response.get("output") or "")[:200]
        return (not is_error), exit_code, snippet
    if isinstance(response, str):
        err = bool(re.search(r"\b(error|failed|permission denied|not found)\b", response, re.I))
        return (not err), (1 if err else 0), response[:200]
    return True, 0, str(response)[:200]


def main() -> int:
    try:
        raw_text = sys.stdin.read()
        payload = json.loads(raw_text) if raw_text.strip() else {}
    except Exception:
        return 0

    session_id = str(payload.get("session_id", "unknown-session"))
    tool_name = str(payload.get("tool_name", ""))
    tool_input = payload.get("tool_input") or {}
    tool_response = payload.get("tool_response")

    sys.path.insert(0, str(Path(__file__).parent.parent))
    try:
        from lsa.drift.redaction import append_redacted_raw_log
        append_redacted_raw_log(STATE_DIR, "PostToolUse", payload)
    except Exception:
        pass

    classified = classify(tool_name, tool_input)
    if classified is None:
        return 0
    target, command, label = classified
    success, exit_code, snippet = parse_tool_response(tool_response)

    event = {
        "function": f"session:{session_id}",
        "event_type": "mutation",
        "target": target,
        "metadata": {
            "tool_name": label,
            "command": command,
            "success": success,
            "exit_code": exit_code,
            "output_snippet": snippet,
        },
    }

    trace_file = STATE_DIR / f"{session_id}.trace.jsonl"
    with trace_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")

    # ── Optional Remote Sync (P1 Item 6) ──────────────────────────────────────
    api_url = os.environ.get("LSA_API_URL")
    if api_url:
        try:
            import urllib.request
            req_data = json.dumps({
                "session_id": session_id,
                "tool_name": tool_name,
                "tool_input": tool_input,
                "tool_response": tool_response,
                "agent_source": "claude_code",
            }).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            api_key = os.environ.get("LSA_API_KEY")
            if api_key:
                headers["X-API-Key"] = api_key
            req = urllib.request.Request(f"{api_url.rstrip('/')}/api/v1/sessions/events", data=req_data, headers=headers)
            urllib.request.urlopen(req, timeout=1.5)
        except Exception:
            pass  # Local file remains reliable cache

    return 0


if __name__ == "__main__":
    sys.exit(main())
