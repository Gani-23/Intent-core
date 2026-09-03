#!/usr/bin/env python3
"""Stop hook.

Runs at the end of a Claude Code turn. Loads this session's declared scope
and observed mutation events, compares them, and -- only if something was
flagged -- writes a short markdown report and prints a summary that Claude
Code surfaces back to the user via systemMessage.

If nothing was flagged, this hook is silent and near-instant. It should
never be the thing that makes agentic coding feel slower.

After reporting, the raw per-session trace/scope files are deleted. This is
deliberate: intent-guard is meant to catch drift at the moment it happens,
not accumulate an ever-growing log directory. Anyone who wants a permanent
audit trail should redirect the printed report to their own storage --
that's a hosted-tier feature, not something to bolt on by default.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(PLUGIN_ROOT))

from lsa.core.models import FunctionIntent  # noqa: E402
from lsa.drift.mutation_rules import MutationComparator, SessionScope  # noqa: E402
from lsa.drift.models import ObservedEvent  # noqa: E402
from lsa.drift.semantic_review import SemanticSessionReviewer  # noqa: E402
from lsa.remediation.llm_client import build_remediation_client  # noqa: E402

STATE_DIR = Path(".intent-guard")


class _Settings:
    """Minimal stand-in for LSA's settings object -- enables multi-provider
    failsafe fallback across Anthropic, OpenAI, Gemini, and Antigravity."""

    def __init__(self) -> None:
        self.remediation_provider = os.environ.get("INTENT_GUARD_PROVIDER", "failsafe")
        self.remediation_model = os.environ.get("INTENT_GUARD_MODEL")
        self.remediation_base_url = os.environ.get("INTENT_GUARD_BASE_URL")
        self.remediation_api_key = (
            os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        )
        self.enable_remediation_model = True
        self.remediation_fallback_enabled = True
        self.remediation_timeout_seconds = 20.0


def load_events(path: Path) -> list[ObservedEvent]:
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(ObservedEvent.from_dict(json.loads(line)))
    return events


def load_scope(path: Path) -> SessionScope:
    if not path.exists():
        return SessionScope(task_text="")
    prompts = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            prompts.append(json.loads(line).get("prompt", ""))
    return SessionScope(task_text="\n".join(prompts))


def main() -> int:
    try:
        raw_text = sys.stdin.read()
        payload = json.loads(raw_text) if raw_text.strip() else {}
    except Exception:
        return 0

    session_id = str(payload.get("session_id", "unknown-session"))
    trace_path = STATE_DIR / f"{session_id}.trace.jsonl"
    scope_path = STATE_DIR / f"{session_id}.scope.jsonl"

    STATE_DIR.mkdir(exist_ok=True)
    raw_log = STATE_DIR / "raw_stdin.jsonl"
    with raw_log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"hook": "Stop", "payload": payload}) + "\n")

    events = load_events(trace_path)
    scope = load_scope(scope_path)

    if not events:
        return 0

    rule_alerts = MutationComparator().compare(scope, events)

    settings = _Settings()
    reviewer = SemanticSessionReviewer(
        model=settings.remediation_model,
        preferred_provider=settings.remediation_provider,
    )
    semantic_alerts = reviewer.review(scope, events)

    seen_targets = {a.observed_target for a in rule_alerts}
    alerts = rule_alerts + [a for a in semantic_alerts if a.observed_target not in seen_targets]

    if alerts:
        alerts = sorted(alerts, key=lambda a: {"critical": 0, "high": 1, "medium": 2}.get(a.severity, 3))
        client = build_remediation_client(_Settings())
        placeholder_function = FunctionIntent(
            name=session_id, module="session", qualname=f"session:{session_id}",
            lineno=0, end_lineno=0,
        )
        lines = [f"# intent-guard session report ({session_id})", ""]
        for alert in alerts:
            prompt = (
                f"Task description:\n{scope.task_text}\n\n"
                f"Flagged action: {alert.observed_target}\nSeverity: {alert.severity}\n"
                f"Reason: {alert.reason}\nWrite a short remediation report."
            )
            report = client.analyze(placeholder_function, alert, prompt)
            lines.append(report.to_markdown())

        report_dir = STATE_DIR / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{session_id}.md"
        report_path.write_text("\n".join(lines), encoding="utf-8")

        summary = (
            f"intent-guard flagged {len(alerts)} action(s) this session "
            f"(highest severity: {alerts[0].severity}). Full report: {report_path}"
        )
        print(json.dumps({"systemMessage": summary}))

    trace_path.unlink(missing_ok=True)
    scope_path.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
