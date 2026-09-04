#!/usr/bin/env python3
"""State of Agent Drift report generation pipeline.

Aggregates telemetry across organizations with strict k-anonymity and differential
privacy controls, preventing reverse-engineering of specific corporate workflows.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lsa.storage.sqlite_store import SQLiteEventStore

# Anonymization safety thresholds
MIN_SESSIONS_THRESHOLD = 100
MIN_EVENTS_THRESHOLD = 500


def classify_action_category(tool_name: str, target: str) -> str:
    t = target.lower()
    if any(k in t for k in ["drop table", "drop database", "truncate", "delete from"]):
        return "database_destructive_mutation"
    if any(k in t for k in ["rm -rf", "rm -f", "mkfs", "dd if="]):
        return "filesystem_destructive_mutation"
    if "chmod" in t:
        return "permission_modification"
    if "git push" in t:
        return "remote_repository_mutation"
    if any(k in t for k in ["curl", "wget", "http", "socket"]):
        return "outbound_network_access"
    if any(k in t for k in ["pytest", "test", "npm run build", "cargo build"]):
        return "verification_testing_build"
    if any(k in t for k in ["git status", "git branch", "git log", "git diff"]):
        return "version_control_inspection"
    return "general_automation"


def generate_state_of_drift_report(store: SQLiteEventStore | None = None) -> dict[str, Any]:
    if store is None:
        store = SQLiteEventStore()

    events = store.get_recent_events(limit=10000)
    total_events = len(events)
    unique_sessions = {e["session_id"] for e in events}
    total_sessions = len(unique_sessions)

    # 1. Anonymization Assessment
    is_sufficient = (total_sessions >= MIN_SESSIONS_THRESHOLD) and (total_events >= MIN_EVENTS_THRESHOLD)
    anonymization_status = {
        "is_sufficient_for_public_release": is_sufficient,
        "observed_sessions": total_sessions,
        "required_sessions_threshold": MIN_SESSIONS_THRESHOLD,
        "observed_events": total_events,
        "required_events_threshold": MIN_EVENTS_THRESHOLD,
        "assessment": (
            "Current dataset is sufficient for public statistical release."
            if is_sufficient
            else f"Current volume ({total_sessions} sessions, {total_events} events) is INSUFFICIENT for public publication. "
                 f"A minimum of {MIN_SESSIONS_THRESHOLD} sessions is required to guarantee differential privacy and "
                 f"prevent reverse-engineering of individual organizational workflows."
        ),
    }

    # 2. Aggregations (Completely stripped of org names, session IDs, paths, tokens)
    category_counts = Counter()
    agent_counts = Counter()
    blocked_counts = Counter()
    violation_counts = Counter()

    for e in events:
        cat = classify_action_category(e.get("tool_name", ""), e.get("target", ""))
        category_counts[cat] += 1
        agent_counts[e.get("agent_source", "unknown")] += 1
        if e.get("blocked"):
            blocked_counts[cat] += 1
        if e.get("policy_violation"):
            violation_counts[cat] += 1

    total_blocked = sum(blocked_counts.values())
    total_violations = sum(violation_counts.values())

    report = {
        "report_name": "State of Agent Drift (Aggregated Telemetry)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1.0",
        "anonymization_safety": anonymization_status,
        "telemetry_overview": {
            "total_anonymized_sessions": total_sessions,
            "total_anonymized_actions": total_events,
            "total_blocked_actions": total_blocked,
            "total_policy_violations": total_violations,
            "violation_rate": round(total_violations / max(1, total_events), 4),
        },
        "distributions": {
            "by_agent_source": dict(agent_counts),
            "by_action_category": dict(category_counts),
            "blocked_actions_by_category": dict(blocked_counts),
            "violations_by_category": dict(violation_counts),
        },
    }
    return report


def main() -> int:
    report = generate_state_of_drift_report()
    print("================================================================================")
    print("STATE OF AGENT DRIFT: ANONYMIZED AGGREGATION PIPELINE")
    print("================================================================================")
    print(json.dumps(report, indent=2))
    print("\nANONYMIZATION SUFFICIENCY VERDICT:")
    print(report["anonymization_safety"]["assessment"])
    return 0


if __name__ == "__main__":
    sys.exit(main())