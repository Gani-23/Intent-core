#!/usr/bin/env python3
"""Secret and credential redaction for event logging and raw telemetry.

Ensures that sensitive data (API keys, private keys, database passwords,
tokens) are never persisted in plaintext in .intent-guard/ telemetry logs.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

# Common high-risk credential patterns
_SECRET_PATTERNS = [
    # Generic password assignments
    (re.compile(r"((?:password|passwd|secret)\s*[=:]\s*['\"]?)([^'\"\s\n]{6,})(['\"]?)", re.I), r"\1[REDACTED_SECRET]\3"),
    # Specific tokens
    (re.compile(r"(sk-[a-zA-Z0-9_\-]{20,})"), "[REDACTED_API_KEY]"),
    (re.compile(r"(gh[pousr][_-][a-zA-Z0-9]{20,})"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"(AIza[0-9A-Za-z-_]{35})"), "[REDACTED_GOOGLE_KEY]"),
    (re.compile(r"(bearer\s+[a-zA-Z0-9_\-\.]{20,})", re.I), "Bearer [REDACTED_TOKEN]"),
    # Private keys
    (re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
    # DB connection URIs with passwords
    (re.compile(r"(postgres(?:ql)?://[^:]+:)([^@]+)(@)", re.I), r"\1[REDACTED_PASSWORD]\3"),
    (re.compile(r"(mysql://[^:]+:)([^@]+)(@)", re.I), r"\1[REDACTED_PASSWORD]\3"),
    (re.compile(r"(mongodb(?:\+srv)?://[^:]+:)([^@]+)(@)", re.I), r"\1[REDACTED_PASSWORD]\3"),
]


def redact_text(text: str) -> str:
    """Redact known secret patterns from an arbitrary text payload."""
    if not text:
        return ""
    result = text
    for pattern, repl in _SECRET_PATTERNS:
        result = pattern.sub(repl, result)
    return result


def redact_json_obj(obj: object) -> object:
    """Recursively redact secrets from dictionary/list objects."""
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, dict):
        new_dict = {}
        for k, v in obj.items():
            # If key indicates a secret, redact entirely if non-empty string
            if re.search(r"^(password|secret|token|api[_-]?key|private[_-]?key)$", str(k), re.I):
                new_dict[k] = "[REDACTED_SECRET]"
            else:
                new_dict[k] = redact_json_obj(v)
        return new_dict
    if isinstance(obj, list):
        return [redact_json_obj(item) for item in obj]
    return obj


def append_redacted_raw_log(state_dir: Path, hook_name: str, payload: dict, max_bytes: int = 5_000_000) -> None:
    """Append redacted payload to raw_stdin.jsonl with size-based rotation."""
    state_dir.mkdir(exist_ok=True)
    raw_log = state_dir / "raw_stdin.jsonl"
    
    # Rotate if exceeds max_bytes
    if raw_log.exists():
        try:
            if raw_log.stat().st_size > max_bytes:
                rotated = state_dir / "raw_stdin.jsonl.1"
                rotated.unlink(missing_ok=True)
                raw_log.rename(rotated)
        except Exception:
            pass

    redacted_payload = redact_json_obj(payload)
    with raw_log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"hook": hook_name, "payload": redacted_payload}) + "\n")
