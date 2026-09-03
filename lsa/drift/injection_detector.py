#!/usr/bin/env python3
"""Prompt injection causal detection.

Detects the pattern: agent reads a file → agent performs an out-of-scope
critical action. This causal sequence is evidence that content in the read
file may have injected new instructions into the agent's context.

No other tool in the observability space reasons about this causally.
This is the gap that distinguishes intent-guard from a static rule scanner.
"""
from __future__ import annotations

import re
from pathlib import Path

from lsa.drift.models import InjectionSignal, ObservedEvent

# Files whose content is likely user-controlled and could contain injections
_SUSPICIOUS_READ_PATTERNS = re.compile(
    r"\.(md|txt|csv|log|html|xml|json|yaml|yml|toml|ini|conf|env)$",
    re.I,
)

# Actions that suggest the agent's scope changed mid-session
_HIGH_RISK_TOOLS = {"Bash", "Write", "Edit", "MultiEdit"}

_CRITICAL_SEVERITIES = {"critical", "high"}

# How many events after a Read to look for triggered actions
_LOOKAHEAD = 5


def _is_in_scope(target: str, authorized_paths: list[str]) -> bool:
    """Return True if target matches any authorized path."""
    if not authorized_paths:
        return False
    for path in authorized_paths:
        if path.lower() in target.lower() or target.lower() in path.lower():
            return True
    return False


def _similarity(a: str, b: str) -> float:
    """Rough token-overlap similarity (no external deps)."""
    tokens_a = set(re.findall(r"\w+", a.lower()))
    tokens_b = set(re.findall(r"\w+", b.lower()))
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / max(len(tokens_a), len(tokens_b))


def detect_injection(
    session_id: str,
    events: list[ObservedEvent],
    authorized_paths: list[str],
    alert_targets: list[str],
) -> list[InjectionSignal]:
    """Analyze event sequence for prompt injection signals.

    Algorithm:
    1. Find Read events on suspicious (user-controlled content) files.
    2. Look at the next _LOOKAHEAD events.
    3. If a high-risk tool fires on a target that is:
       - NOT in the original authorized scope, AND
       - NOT similar to the Read target (so it's a new, unrelated target)
       - Has appeared in drift alerts
    → Injection signal with confidence based on proximity and scope deviation.
    """
    signals: list[InjectionSignal] = []
    alert_set = set(alert_targets)

    for i, event in enumerate(events):
        tool = event.metadata.get("tool_name", "")
        if tool != "Read" and not event.target.startswith("/"):
            continue
        if not _SUSPICIOUS_READ_PATTERNS.search(event.target):
            continue

        # Look at next _LOOKAHEAD events for triggered suspicious actions
        window = events[i + 1: i + 1 + _LOOKAHEAD]
        for j, follow in enumerate(window):
            follow_tool = follow.metadata.get("tool_name", "")
            if follow_tool not in _HIGH_RISK_TOOLS:
                continue
            if _is_in_scope(follow.target, authorized_paths):
                continue  # In-scope action after Read is normal
            if follow.target not in alert_set:
                continue  # Only flag if it already raised a drift alert

            # Compute confidence: higher if closer and more out-of-scope
            proximity_score = 1.0 - (j / _LOOKAHEAD)
            scope_divergence = 1.0 - _similarity(event.target, follow.target)
            confidence = round(min(1.0, proximity_score * 0.5 + scope_divergence * 0.5), 2)

            if confidence >= 0.3:
                signals.append(InjectionSignal(
                    read_target=event.target,
                    triggered_action=follow.target,
                    confidence=confidence,
                    session_id=session_id,
                ))

    return signals
