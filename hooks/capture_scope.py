#!/usr/bin/env python3
"""UserPromptSubmit hook.

Reads the JSON Claude Code sends on stdin for this event, pulls out the raw
prompt text, and appends it to a small per-session scope file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

STATE_DIR = Path(".intent-guard")


def main() -> int:
    try:
        raw_text = sys.stdin.read()
        payload = json.loads(raw_text) if raw_text.strip() else {}
    except Exception:
        return 0

    session_id = str(payload.get("session_id", "unknown-session"))
    prompt_text = str(payload.get("prompt", ""))

    STATE_DIR.mkdir(exist_ok=True)
    raw_log = STATE_DIR / "raw_stdin.jsonl"
    with raw_log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"hook": "UserPromptSubmit", "payload": payload}) + "\n")

    if not prompt_text.strip():
        return 0

    scope_file = STATE_DIR / f"{session_id}.scope.jsonl"
    with scope_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"prompt": prompt_text}) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
