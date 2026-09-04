#!/usr/bin/env python3
"""PreToolUse hook — fast deterministic blocker (strict mode only).

In OBSERVE mode (default): logs the incoming action and returns exit 0.
In STRICT mode (INTENT_GUARD_MODE=strict): evaluates highest-risk patterns
against the signed scope manifest and returns {"continue": false, "reason": "..."}
to block the tool call BEFORE it executes.

This is the only hook in intent-guard that can actually prevent damage.
It is deliberately opt-in to preserve observe-only ergonomics (Rule 6).

Sub-100ms: no LLM calls, no disk reads beyond the scope/sig files.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

STATE_DIR = Path(".intent-guard")
_STRICT = os.environ.get("INTENT_GUARD_MODE", "").lower() == "strict"
# Verification error policy: default fail-open for local developer convenience,
# fail-closed when INTENT_GUARD_FAIL_CLOSED=true or under strict enterprise policy.
_FAIL_CLOSED = os.environ.get("INTENT_GUARD_FAIL_CLOSED", "false").lower() in ("true", "1", "yes")

# Highest-risk patterns that warrant blocking even pre-execution
# These are a stricter subset of DESTRUCTIVE_PATTERNS in mutation_rules.py
_CRITICAL_BLOCK_PATTERNS = [
    (r"rm\s+-rf\s+/",         "filesystem-wide recursive delete at /"),
    (r"DROP\s+TABLE",          "database table destruction"),
    (r"TRUNCATE\s+TABLE",      "database table truncation"),
    (r"DROP\s+DATABASE",       "database destruction"),
    (r"git\s+push\s+--force",  "force-push to git remote"),
    (r"mkfs\b",                "filesystem format"),
    (r"dd\s+if=.*of=/dev/",    "raw device write"),
    (r":\(\)\{.*\}:;",         "fork bomb"),
]


def _load_scope_text(session_id: str) -> str:
    scope_path = STATE_DIR / f"{session_id}.scope.jsonl"
    if not scope_path.exists():
        return ""
    lines = []
    for line in scope_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                lines.append(json.loads(line).get("prompt", ""))
            except Exception:
                pass
    return "\n".join(lines)


def _verify_scope_signature(session_id: str, task_text: str) -> tuple[bool, str]:
    """Check HMAC sig without importing from lsa (hooks run standalone)."""
    import hmac, hashlib
    sig_path = STATE_DIR / f"{session_id}.sig"
    key_path = STATE_DIR / "machine.key"
    if not sig_path.exists() or not key_path.exists():
        if _FAIL_CLOSED and _STRICT:
            return False, "sig file or key missing under fail-closed policy"
        return True, "unsigned (first session or key missing)"
    try:
        key = bytes.fromhex(key_path.read_text().strip())
        stored_sig = json.loads(sig_path.read_text()).get("sig", "")
        payload = json.dumps({"task": task_text, "session": session_id},
                             separators=(",", ":"), sort_keys=True).encode()
        expected = hmac.new(key, payload, "sha256").hexdigest()
        ok = hmac.compare_digest(expected, stored_sig)
        return ok, "ok" if ok else "HMAC mismatch — scope text modified"
    except Exception as e:
        if _FAIL_CLOSED:
            return False, f"verify error under fail-closed policy: {e}"
        return True, f"verify error: {e}"


def _matches_critical(command: str) -> tuple[bool, str]:
    import re
    for pattern, label in _CRITICAL_BLOCK_PATTERNS:
        if re.search(pattern, command, re.I):
            return True, label
    return False, ""


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0

    session_id = str(payload.get("session_id", "unknown-session"))
    tool_name = str(payload.get("tool_name", ""))
    tool_input = payload.get("tool_input") or {}

    # ── Log raw stdin for envelope inspection with redaction ──────────────────
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from lsa.drift.redaction import append_redacted_raw_log
        append_redacted_raw_log(STATE_DIR, "PreToolUse", payload)
    except Exception:
        pass

    if tool_name != "Bash":
        return 0  # Only block Bash — file edits go through PostToolUse

    command = str(tool_input.get("command", ""))
    if not command:
        return 0

    # ── Always log to trace ───────────────────────────────────────────────────
    try:
        with (STATE_DIR / f"{session_id}.pretool.jsonl").open("a") as f:
            f.write(json.dumps({"tool": tool_name, "command": command[:200]}) + "\n")
    except Exception:
        pass

    if not _STRICT:
        return 0  # Observe-only mode — never block

    # ── STRICT MODE: verify scope integrity then check critical patterns ──────
    task_text = _load_scope_text(session_id)
    sig_ok, sig_reason = _verify_scope_signature(session_id, task_text)
    if not sig_ok:
        result = json.dumps({
            "continue": False,
            "reason": f"[intent-guard strict] SCOPE INTEGRITY VIOLATION: {sig_reason}. Blocking tool execution.",
        })
        sys.stdout.write(result)
        return 0

    matched, label = _matches_critical(command)
    if matched:
        result = json.dumps({
            "continue": False,
            "reason": (
                f"[intent-guard strict] Blocked '{label}' pattern before execution. "
                f"To allow, disable strict mode (unset INTENT_GUARD_MODE=strict) "
                f"or add this command to your session scope explicitly."
            ),
        })
        sys.stdout.write(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
