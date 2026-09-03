#!/usr/bin/env python3
"""UserPromptSubmit hook.

Reads the JSON Claude Code sends on stdin for this event, pulls out the raw
prompt text, and appends it to a small per-session scope file. This is the
only place intent-guard learns what the human actually asked for -- there is
no separate policy file to maintain.

Field names below (`prompt`, `session_id`) follow the current Claude Code
hooks reference as of this writing. If Anthropic changes the schema, this is
the one file that needs updating -- verify against
https://code.claude.com/docs/en/hooks before relying on this in production.

Exit code 0 always: this hook only observes, it never blocks a prompt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

STATE_DIR = Path(".intent-guard")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    session_id = str(payload.get("session_id", "unknown-session"))
    prompt_text = str(payload.get("prompt", ""))
    if not prompt_text.strip():
        return 0

    STATE_DIR.mkdir(exist_ok=True)
    scope_file = STATE_DIR / f"{session_id}.scope.jsonl"
    with scope_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"prompt": prompt_text}) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
