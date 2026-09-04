#!/usr/bin/env python3
"""HMAC-SHA256 intent manifest signing.

Provides tamper-evident integrity checking for the original task description.
Detects inadvertent modification, race conditions, or accidental scope rewrites
between UserPromptSubmit and PreToolUse/Stop checks.

SECURITY BOUNDARY NOTE:
In local-only developer deployment, the signing key lives at .intent-guard/machine.key
and is accessible by the local user process. Therefore, this mechanism provides
tamper-evident integrity against accidental modification, not cryptographic non-repudiation
against a co-resident adversarial process. Full adversarial isolation requires out-of-process
daemon custody or remote signature verification (planned for enterprise backend).
"""
from __future__ import annotations

import hmac
import json
import secrets
from pathlib import Path

STATE_DIR = Path(".intent-guard")
KEY_FILE = STATE_DIR / "machine.key"
_ALGORITHM = "sha256"


def get_or_create_machine_key() -> bytes:
    """Load the machine-local signing key, creating it on first use.
    Presence is boolean-checked; value is never logged (Rule 8).
    """
    STATE_DIR.mkdir(exist_ok=True)
    if KEY_FILE.exists():
        raw = KEY_FILE.read_text().strip()
        if len(raw) == 64:
            return bytes.fromhex(raw)
    key = secrets.token_bytes(32)
    KEY_FILE.write_text(key.hex())
    KEY_FILE.chmod(0o600)
    return key


def _canonical(task_text: str, session_id: str) -> bytes:
    payload = json.dumps({"task": task_text, "session": session_id},
                         separators=(",", ":"), sort_keys=True)
    return payload.encode()


def sign_manifest(task_text: str, session_id: str) -> str:
    """Return hex HMAC-SHA256 over (task_text, session_id)."""
    key = get_or_create_machine_key()
    mac = hmac.new(key, _canonical(task_text, session_id), _ALGORITHM)
    return mac.hexdigest()


def verify_manifest(task_text: str, session_id: str, signature: str) -> bool:
    """Constant-time HMAC verify. Returns True iff signature is valid."""
    if not KEY_FILE.exists():
        return False
    try:
        key = get_or_create_machine_key()
        expected = hmac.new(key, _canonical(task_text, session_id), _ALGORITHM)
        return hmac.compare_digest(expected.hexdigest(), signature)
    except Exception:
        return False


def write_sig_file(session_id: str, task_text: str) -> Path:
    """Sign and persist a .sig file alongside the scope file."""
    STATE_DIR.mkdir(exist_ok=True)
    sig = sign_manifest(task_text, session_id)
    sig_path = STATE_DIR / f"{session_id}.sig"
    sig_path.write_text(json.dumps({"sig": sig, "session_id": session_id}))
    return sig_path


def verify_sig_file(session_id: str, task_text: str) -> tuple[bool, str]:
    """Verify persisted .sig file. Returns (ok, reason)."""
    sig_path = STATE_DIR / f"{session_id}.sig"
    if not sig_path.exists():
        return False, "sig file missing — scope may be unsigned or tampered"
    try:
        data = json.loads(sig_path.read_text())
        sig = data.get("sig", "")
    except Exception:
        return False, "sig file unreadable"
    if verify_manifest(task_text, session_id, sig):
        return True, "ok"
    return False, "HMAC mismatch — scope text does not match original signed manifest"


def key_is_present() -> bool:
    """Boolean check — key exists. Never exposes the value (Rule 8)."""
    return KEY_FILE.exists() and len(KEY_FILE.read_text().strip()) == 64
