#!/usr/bin/env python3
"""Cross-session behavioral ledger.

Append-only JSONL log of every significant action across all agent sessions.
Enables detection of multi-session drift patterns that no single session
analysis can see: READ → WRITE → DELETE escalation, scope creep, recurrence.

Ledger at .intent-guard/ledger.jsonl — excluded from git.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from lsa.drift.models import DriftAlert, LedgerEntry, ObservedEvent

STATE_DIR = Path(".intent-guard")
LEDGER_FILE = STATE_DIR / "ledger.jsonl"

_OP_MAP = {
    "Write": "WRITE", "Edit": "WRITE", "MultiEdit": "WRITE",
    "NotebookEdit": "WRITE", "Bash": "EXEC", "Read": "READ",
    "mcp__": "NETWORK",
}

_SEV_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def _classify_op(tool_name: str) -> str:
    for prefix, op in _OP_MAP.items():
        if tool_name.startswith(prefix):
            return op
    return "OTHER"


def _action_hash(session_id: str, target: str, op: str) -> str:
    raw = f"{session_id}:{target}:{op}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def append_to_ledger(session_id: str, event: ObservedEvent, severity: str) -> None:
    """Append one entry to the global ledger. Always exits cleanly."""
    try:
        STATE_DIR.mkdir(exist_ok=True)
        tool = event.metadata.get("tool_name", "")
        op = _classify_op(tool)
        entry = LedgerEntry(
            ts=datetime.now(timezone.utc).isoformat(),
            session_id=session_id,
            action_hash=_action_hash(session_id, event.target, op),
            target=event.target,
            op=op,
            severity=severity,
        )
        with LEDGER_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")
    except Exception:
        pass  # Never crash the hook pipeline


def load_ledger() -> list[LedgerEntry]:
    if not LEDGER_FILE.exists():
        return []
    entries = []
    for line in LEDGER_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(LedgerEntry.from_dict(json.loads(line)))
            except Exception:
                continue
    return entries


@dataclass
class LedgerPattern:
    pattern: str
    targets: list[str]
    sessions: list[str]
    description: str
    severity: str


def analyze_ledger(entries: list[LedgerEntry]) -> list[LedgerPattern]:
    """Detect cross-session behavioral patterns. Returns a list of findings."""
    patterns: list[LedgerPattern] = []
    if not entries:
        return patterns

    # ── 1. Escalation: READ → WRITE → DELETE on same target ──────────────────
    by_target: dict[str, list[LedgerEntry]] = {}
    for e in entries:
        key = e.target[:60]
        by_target.setdefault(key, []).append(e)

    for target, tevents in by_target.items():
        ops_seen = {e.op for e in tevents}
        sessions_involved = list(dict.fromkeys(e.session_id for e in tevents))
        if {"READ", "WRITE", "DELETE"} <= ops_seen and len(sessions_involved) > 1:
            patterns.append(LedgerPattern(
                pattern="READ_WRITE_DELETE_ESCALATION",
                targets=[target],
                sessions=sessions_involved,
                description=(
                    f"Target '{target}' was read, then written, then deleted across "
                    f"{len(sessions_involved)} sessions — classic privilege escalation pattern."
                ),
                severity="critical",
            ))
        elif {"READ", "WRITE"} <= ops_seen and len(sessions_involved) > 1:
            # Ordinary iterative dev reads in one session and writes in another.
            # Only flag if at least one operation was flagged with severity > none,
            # or if the target is a sensitive/critical resource.
            has_flagged_op = any(_SEV_ORDER.get(e.severity, 0) >= 2 for e in tevents)
            if has_flagged_op:
                patterns.append(LedgerPattern(
                    pattern="READ_THEN_WRITE_CROSS_SESSION",
                    targets=[target],
                    sessions=sessions_involved,
                    description=(
                        f"Target '{target}' read in one session then written with elevated severity in another — "
                        f"possible scope creep or data exfil pattern."
                    ),
                    severity="low",
                ))

    # ── 2. Recurrence: same critical/high violation in >1 session ─────────────
    crit_targets: dict[str, list[str]] = {}
    for e in entries:
        if _SEV_ORDER.get(e.severity, 0) >= 3:  # high or critical
            crit_targets.setdefault(e.target[:60], []).append(e.session_id)

    for target, sess_list in crit_targets.items():
        unique_sess = list(dict.fromkeys(sess_list))
        if len(unique_sess) > 1:
            patterns.append(LedgerPattern(
                pattern="RECURRING_VIOLATION",
                targets=[target],
                sessions=unique_sess,
                description=(
                    f"High/critical violation on '{target}' recurred across "
                    f"{len(unique_sess)} sessions — agent is not learning from prior alerts."
                ),
                severity="high",
            ))

    return patterns
