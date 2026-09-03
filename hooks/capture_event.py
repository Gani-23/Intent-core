#!/usr/bin/env python3
"""PostToolUse hook.

Reads the tool-call JSON Claude Code sends on stdin, classifies it into a
small ObservedEvent, and appends ONE line of JSON to a per-session trace
file. Deliberately captures paths and commands, never full file contents or
diffs -- this is the fix for the GB-scale-log problem: a session's entire
trace file should be kilobytes, not megabytes, because we only ever store
metadata about what happened, not the data itself.

Exit code 0 always: this hook only observes, it never blocks a tool call.
Blocking (deny on the high-risk patterns) is a natural v2 addition once the
detection logic has real sessions behind it -- shipping it as observe-only
first means adopting this tool costs nothing and can't break anyone's flow.
"""
from __future__ import annotations

import json
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


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    session_id = str(payload.get("session_id", "unknown-session"))
    tool_name = str(payload.get("tool_name", ""))
    tool_input = payload.get("tool_input") or {}

    classified = classify(tool_name, tool_input)
    if classified is None:
        return 0
    target, command, label = classified

    event = {
        "function": f"session:{session_id}",
        "event_type": "mutation",
        "target": target,
        "metadata": {"tool_name": label, "command": command},
    }

    STATE_DIR.mkdir(exist_ok=True)
    trace_file = STATE_DIR / f"{session_id}.trace.jsonl"
    with trace_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
