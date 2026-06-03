from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _is_non_ok_outcome(value: object) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized in {"error", "failed", "denied", "blocked", "rejected"}


@dataclass(slots=True)
class PrivilegedApiAuditSummary:
    generated_at: str
    window_hours: float
    total_entries: int
    recent_entries: int
    non_ok_recent_entries: int
    denied_recent_entries: int
    blocked_recent_entries: int
    rejected_recent_entries: int
    top_actions: list[dict[str, object]] = field(default_factory=list)
    top_roles: list[dict[str, object]] = field(default_factory=list)
    sample_non_ok_entries: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "window_hours": self.window_hours,
            "total_entries": self.total_entries,
            "recent_entries": self.recent_entries,
            "non_ok_recent_entries": self.non_ok_recent_entries,
            "denied_recent_entries": self.denied_recent_entries,
            "blocked_recent_entries": self.blocked_recent_entries,
            "rejected_recent_entries": self.rejected_recent_entries,
            "top_actions": [dict(item) for item in self.top_actions],
            "top_roles": [dict(item) for item in self.top_roles],
            "sample_non_ok_entries": [dict(item) for item in self.sample_non_ok_entries],
        }


@dataclass(slots=True)
class PrivilegedApiAuditPruneResult:
    pruned_at: str
    retention_days: int
    before_count: int
    after_count: int
    pruned_count: int
    cutoff_timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "pruned_at": self.pruned_at,
            "retention_days": self.retention_days,
            "before_count": self.before_count,
            "after_count": self.after_count,
            "pruned_count": self.pruned_count,
            "cutoff_timestamp": self.cutoff_timestamp,
        }


@dataclass(slots=True)
class PrivilegedApiAuditService:
    log_path: Path

    def list_entries(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        entries = self._load_entries()
        if limit is None:
            return entries
        return entries[-limit:]

    def build_summary(self, *, window_hours: float = 24.0) -> PrivilegedApiAuditSummary:
        now = _utc_now()
        cutoff = now - timedelta(hours=window_hours)
        entries = self._load_entries()
        recent_entries = [
            entry for entry in entries if (_parse_timestamp(str(entry.get("recorded_at") or "")) or now) >= cutoff
        ]
        non_ok_entries = [entry for entry in recent_entries if _is_non_ok_outcome(entry.get("outcome"))]
        action_counts: dict[str, int] = {}
        role_counts: dict[str, int] = {}
        denied_count = 0
        blocked_count = 0
        rejected_count = 0
        for entry in recent_entries:
            action = str(entry.get("action") or "unknown")
            action_counts[action] = action_counts.get(action, 0) + 1
            role = str(dict(entry.get("actor") or {}).get("role") or "unknown")
            role_counts[role] = role_counts.get(role, 0) + 1
            outcome = str(entry.get("outcome") or "").strip().lower()
            if outcome == "denied":
                denied_count += 1
            elif outcome == "blocked":
                blocked_count += 1
            elif outcome == "rejected":
                rejected_count += 1
        top_actions = [
            {"action": action, "count": count}
            for action, count in sorted(action_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
        ]
        top_roles = [
            {"role": role, "count": count}
            for role, count in sorted(role_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
        ]
        return PrivilegedApiAuditSummary(
            generated_at=now.isoformat(),
            window_hours=window_hours,
            total_entries=len(entries),
            recent_entries=len(recent_entries),
            non_ok_recent_entries=len(non_ok_entries),
            denied_recent_entries=denied_count,
            blocked_recent_entries=blocked_count,
            rejected_recent_entries=rejected_count,
            top_actions=top_actions,
            top_roles=top_roles,
            sample_non_ok_entries=non_ok_entries[-5:],
        )

    def prune(self, *, retention_days: int) -> PrivilegedApiAuditPruneResult:
        now = _utc_now()
        cutoff = now - timedelta(days=retention_days)
        entries = self._load_entries()
        kept = [
            entry
            for entry in entries
            if (_parse_timestamp(str(entry.get("recorded_at") or "")) or now) >= cutoff
        ]
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("w", encoding="utf-8") as handle:
            for entry in kept:
                handle.write(json.dumps(entry, sort_keys=True) + "\n")
        return PrivilegedApiAuditPruneResult(
            pruned_at=now.isoformat(),
            retention_days=retention_days,
            before_count=len(entries),
            after_count=len(kept),
            pruned_count=len(entries) - len(kept),
            cutoff_timestamp=cutoff.isoformat(),
        )

    def _load_entries(self) -> list[dict[str, Any]]:
        if not self.log_path.exists():
            return []
        entries: list[dict[str, Any]] = []
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entries.append(dict(json.loads(line)))
            except json.JSONDecodeError:
                continue
        return entries
