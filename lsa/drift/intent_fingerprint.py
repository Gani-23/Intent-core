#!/usr/bin/env python3
"""Structural intent fingerprinting.

Parses a raw task prompt into an IntentFingerprint: a CRUD-matrix of what
ops are authorized, which paths/tables are in scope, and what is explicitly
prohibited. This replaces naive keyword matching with a semantic operation
model, enabling the comparator to flag actions that violate the *structure*
of the intent, not just its surface wording.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── op classifier patterns ────────────────────────────────────────────────────
_OP_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("READ",    re.compile(r"\b(read|fetch|audit|inspect|view|look|check|get|list|scan|review)\b", re.I)),
    ("WRITE",   re.compile(r"\b(write|update|modify|edit|change|set|save|create|add|insert|patch)\b", re.I)),
    ("DELETE",  re.compile(r"\b(delete|remove|drop|purge|clean|wipe|erase|truncate)\b", re.I)),
    ("EXEC",    re.compile(r"\b(run|execute|apply|deploy|migrate|restart|start|stop|install)\b", re.I)),
    ("NETWORK", re.compile(r"\b(call|fetch|request|download|upload|sync|push|pull|send|connect)\b", re.I)),
]

# ── prohibition extractors ────────────────────────────────────────────────────
_PROHIB_PREFIX = re.compile(
    r"(do\s+not|don'?t|never|without\s+(?:prior\s+)?approval|must\s+not|no\s+[\w\s]+(?:writes?|delete|modify|exec))",
    re.I,
)
_PATH_PATTERN  = re.compile(r"([\w./-]+\.(?:env|json|yaml|yml|py|sql|sh|tf|ts|js|go|rs|toml)|\b(?:production|prod|main|master)\b)", re.I)
_TABLE_PATTERN = re.compile(r"\b(users?|accounts?|orders?|payments?|transactions?|sessions?|tokens?|logs?|audit)\b", re.I)

# ── constraint phrases (kept for backward compat) ─────────────────────────────
_CONSTRAINT_PHRASES = [
    r"do\s+not\s+(?:touch|modify|change|delete|write)",
    r"read[- ]only",
    r"without\s+(?:prior\s+)?approval",
    r"do\s+not\s+run\s+destructive",
    r"never\s+(?:touch|modify|delete|drop|truncate)",
    r"must\s+not\s+(?:modify|delete|write)",
]
_CONSTRAINT_RE = re.compile("|".join(_CONSTRAINT_PHRASES), re.I)

# Broad negative-scope phrases that enforce strict read-only operation
_READ_ONLY_PHRASES = [
    r"\bread[- ]only\b",
    r"\bnever\s+modify\b",
    r"\bdo\s+not\s+(?:modify|change|edit|write|alter|touch)\b",
    r"\bdon'?t\s+(?:modify|change|edit|write|alter|touch)\b",
    r"\bmust\s+not\s+(?:modify|change|edit|write|alter|touch)\b",
    r"\bno\s+writes?\b",
    r"\bno\s+modifications?\b",
    r"\bdon'?t\s+touch\s+anything\b",
    r"\bdo\s+not\s+touch\s+anything\b",
    r"\bnever\s+touch\s+anything\b",
    r"\bonly\s+read\b",
    r"\bjust\s+read\b",
]
_READ_ONLY_RE = re.compile("|".join(_READ_ONLY_PHRASES), re.I)


@dataclass
class IntentFingerprint:
    """Structured representation of what a task prompt authorizes."""
    authorized_ops: set[str] = field(default_factory=set)
    authorized_paths: list[str] = field(default_factory=list)
    authorized_tables: list[str] = field(default_factory=list)
    prohibitions: list[str] = field(default_factory=list)
    read_only: bool = False
    confidence: float = 0.0

    def authorizes(self, op: str) -> bool:
        if self.read_only and op in ("WRITE", "DELETE"):
            return False
        return op in self.authorized_ops

    def explicitly_prohibits(self, action_text: str) -> str | None:
        """Return the matching prohibition phrase, or None."""
        for p in self.prohibitions:
            if re.search(re.escape(p[:30]), action_text, re.I):
                return p
        return None

    def to_dict(self) -> dict:
        return {
            "authorized_ops": sorted(self.authorized_ops),
            "authorized_paths": self.authorized_paths,
            "authorized_tables": self.authorized_tables,
            "prohibitions": self.prohibitions,
            "read_only": self.read_only,
            "confidence": self.confidence,
        }


def extract_fingerprint(task_text: str) -> IntentFingerprint:
    """Parse a raw task prompt into a structured IntentFingerprint.

    Runs entirely in stdlib — no LLM call needed.
    """
    fp = IntentFingerprint()
    if not task_text.strip():
        return fp

    # ── 1. Split into sentences and classify each ──────────────────────────────
    sentences = re.split(r"[.;!\n]", task_text)
    negated: list[str] = []
    affirmative: list[str] = []
    for sent in sentences:
        if _PROHIB_PREFIX.search(sent):
            negated.append(sent)
        else:
            affirmative.append(sent)

    # ── 2. Extract authorized ops only from affirmative sentences ─────────────
    # Bug fix: never add an op from a sentence that begins with a prohibition.
    affirmative_text = " ".join(affirmative)
    for op, pat in _OP_PATTERNS:
        if pat.search(affirmative_text):
            fp.authorized_ops.add(op)

    # ── 2. Extract path references ────────────────────────────────────────────
    fp.authorized_paths = list(dict.fromkeys(_PATH_PATTERN.findall(task_text)))

    # ── 3. Extract table references ───────────────────────────────────────────
    fp.authorized_tables = list(dict.fromkeys(
        m.lower() for m in _TABLE_PATTERN.findall(task_text)
    ))

    # ── 4. Extract prohibitions (from negated sentences already identified) ────
    for sent in negated:
        cleaned = sent.strip()
        if cleaned:
            fp.prohibitions.append(cleaned)

    # ── 5. Legacy constraint phrase check (keeps backward compat) ─────────────
    for m in _CONSTRAINT_RE.finditer(task_text):
        phrase = m.group(0).strip()
        if phrase not in fp.prohibitions:
            fp.prohibitions.append(phrase)

    # ── 6. Broad negative-scope (read-only) extraction ─────────────────────────
    if bool(_READ_ONLY_RE.search(task_text)):
        fp.read_only = True
        # If read_only is declared, WRITE and DELETE can never be authorized ops
        fp.authorized_ops.discard("WRITE")
        fp.authorized_ops.discard("DELETE")

    # ── 7. Confidence heuristic ───────────────────────────────────────────────
    score = 0.0
    if fp.authorized_ops:
        score += 0.3
    if fp.authorized_paths or fp.authorized_tables:
        score += 0.3
    if fp.prohibitions or fp.read_only:
        score += 0.4
    # More specific = higher confidence
    if len(fp.authorized_ops) == 1:
        score = min(1.0, score + 0.1)
    fp.confidence = round(min(1.0, score), 2)

    return fp
