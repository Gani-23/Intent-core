#!/usr/bin/env python3
"""UserPromptSubmit hook — captures task scope, signs manifest, generates invariants."""
from __future__ import annotations

import json
import os
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

    sys.path.insert(0, str(Path(__file__).parent.parent))
    try:
        from lsa.drift.redaction import append_redacted_raw_log
        append_redacted_raw_log(STATE_DIR, "UserPromptSubmit", payload)
    except Exception:
        pass

    if not prompt_text.strip():
        return 0

    # ── 1. Write scope file ───────────────────────────────────────────────────
    scope_file = STATE_DIR / f"{session_id}.scope.jsonl"
    with scope_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"prompt": prompt_text}) + "\n")

    # ── 2. Sign the manifest (HMAC) ───────────────────────────────────────────
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from lsa.drift.manifest_signer import write_sig_file
        write_sig_file(session_id, prompt_text)
    except Exception:
        pass

    # ── 3. Generate and save invariants ──────────────────────────────────────
    try:
        from lsa.drift.intent_fingerprint import extract_fingerprint
        from lsa.drift.invariant_checker import generate_invariants, save_invariants
        fp = extract_fingerprint(prompt_text)
        invariants = generate_invariants(fp)
        save_invariants(session_id, invariants)
    except Exception:
        pass

    # ── 4. Pull Org Policy-as-Code (L2.1) ─────────────────────────────────────
    api_url = os.environ.get("LSA_API_URL")
    org_name = os.environ.get("LSA_ORG", "default")
    api_key = os.environ.get("LSA_API_KEY")
    if api_url:
        try:
            import urllib.request
            headers = {}
            if api_key:
                headers["X-API-Key"] = api_key
            req = urllib.request.Request(
                f"{api_url.rstrip('/')}/api/v1/orgs/{org_name}/policy",
                headers=headers,
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    policy_data = json.loads(resp.read().decode("utf-8"))
                    policy_cache = STATE_DIR / f"{session_id}.policy.json"
                    policy_cache.write_text(json.dumps(policy_data), encoding="utf-8")
        except Exception:
            pass  # Fail open on network glitch for policy fetch

    return 0


if __name__ == "__main__":
    sys.exit(main())
