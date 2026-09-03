#!/usr/bin/env python3
"""Intent invariant auto-generation and pre-flight contract checking.

Generates a set of Invariant objects from an IntentFingerprint at
UserPromptSubmit time. These are stored alongside the scope file and checked
at Stop time — giving a second, independent alert source beyond mutation rules.

The key insight: invariants are derived from the original signed intent,
not from observed actions. They're a pre-stated contract, not a post-hoc rule.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from lsa.drift.intent_fingerprint import IntentFingerprint
from lsa.drift.models import Invariant, InvariantViolation, ObservedEvent

STATE_DIR = Path(".intent-guard")

# Maps prohibition keyword → (op_class, pattern fragment)
_PROHIB_OP_MAP = [
    (re.compile(r"\b(delete|drop|truncate|remove|erase|wipe)\b", re.I), "NEVER_DELETE", r"\b(rm|unlink|DROP|TRUNCATE|DELETE\s+FROM|rmdir)\b"),
    (re.compile(r"\b(run|execute|exec|apply|deploy|migrate)\b", re.I),  "NEVER_EXEC",   r"\b(bash|sh|exec|subprocess|os\.system|migrate|deploy)\b"),
    (re.compile(r"\b(write|modify|edit|change|update)\b", re.I),        "NEVER_WRITE_PATH", r""),
    (re.compile(r"\b(network|connect|request|call|send|upload)\b", re.I), "NEVER_NETWORK", r"\b(curl|wget|requests\.|urllib|fetch|http)\b"),
]


def generate_invariants(fp: IntentFingerprint) -> list[Invariant]:
    """Derive a list of Invariant objects from an IntentFingerprint."""
    invariants: list[Invariant] = []

    for prohibition in fp.prohibitions:
        lower = prohibition.lower()

        for keyword_pat, op_class, default_pattern in _PROHIB_OP_MAP:
            if keyword_pat.search(lower):
                # Use specific path refs from the fingerprint if available
                if op_class == "NEVER_WRITE_PATH" and fp.authorized_paths:
                    for path in fp.authorized_paths:
                        # Negate: if fingerprint says "do not modify X.env" build an invariant on that file
                        safe_path = re.escape(path)
                        invariants.append(Invariant(
                            description=f"Must not write to '{path}' (stated: '{prohibition[:60]}')",
                            op_class=op_class,
                            pattern_str=safe_path,
                            is_hard=True,
                        ))
                elif default_pattern:
                    invariants.append(Invariant(
                        description=f"Prohibited action: '{prohibition[:80]}'",
                        op_class=op_class,
                        pattern_str=default_pattern,
                        is_hard=True,
                    ))
                break

    # Always add a generic "no production destroy" invariant if prod is mentioned
    text_combined = " ".join(fp.prohibitions)
    if re.search(r"\b(production|prod)\b", text_combined, re.I):
        invariants.append(Invariant(
            description="Never execute destructive operations on production systems",
            op_class="NEVER_EXEC",
            pattern_str=r"\b(DROP|TRUNCATE|DELETE\s+FROM|rm\s+-rf|migrate\s+reset)\b",
            is_hard=True,
        ))

    return invariants


def save_invariants(session_id: str, invariants: list[Invariant]) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    path = STATE_DIR / f"{session_id}.invariants.json"
    path.write_text(json.dumps([i.to_dict() for i in invariants], indent=2))


def load_invariants(session_id: str) -> list[Invariant]:
    path = STATE_DIR / f"{session_id}.invariants.json"
    if not path.exists():
        return []
    try:
        return [Invariant.from_dict(d) for d in json.loads(path.read_text())]
    except Exception:
        return []


def check_invariants(
    session_id: str,
    events: list[ObservedEvent],
    invariants: list[Invariant],
) -> list[InvariantViolation]:
    """Check observed events against pre-stated invariants."""
    violations: list[InvariantViolation] = []
    for inv in invariants:
        if not inv.pattern_str:
            continue
        try:
            pat = re.compile(inv.pattern_str, re.I)
        except re.error:
            continue
        for event in events:
            haystack = f"{event.target} {event.metadata.get('command', '')}"
            if pat.search(haystack):
                violations.append(InvariantViolation(
                    invariant_description=inv.description,
                    observed_target=event.target,
                    session_id=session_id,
                    severity="critical" if inv.is_hard else "medium",
                ))
    return violations
