#!/usr/bin/env python3
"""Stop hook — runs v2 full analysis pipeline at session end.

Pass 1: Regex mutation rules (mutation_rules.py + IntentFingerprint)
Pass 2: Semantic LLM review (multi-provider failsafe)
Pass 3: Invariant violations (pre-stated contracts)
Pass 4: Prompt injection signals (causal Read → action analysis)
Pass 5: Cross-session ledger update + pattern analysis

Exit code 0 always: observe-only, never blocks.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(PLUGIN_ROOT))

from lsa.core.models import FunctionIntent
from lsa.drift.mutation_rules import MutationComparator, SessionScope
from lsa.drift.models import ObservedEvent
from lsa.drift.semantic_review import SemanticSessionReviewer
from lsa.drift.intent_fingerprint import extract_fingerprint
from lsa.drift.invariant_checker import check_invariants, load_invariants
from lsa.drift.injection_detector import detect_injection
from lsa.drift.session_ledger import append_to_ledger, load_ledger, analyze_ledger
from lsa.drift.syscall_bridge import observe_process
from lsa.remediation.llm_client import build_remediation_client

STATE_DIR = Path(".intent-guard")


class _Settings:
    def __init__(self) -> None:
        provider = os.environ.get("INTENT_GUARD_PROVIDER", "failsafe")
        self.remediation_provider = provider
        self.preferred_provider = provider
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
            try:
                events.append(ObservedEvent.from_dict(json.loads(line)))
            except Exception:
                pass
    return events


def load_scope_text(path: Path) -> str:
    if not path.exists():
        return ""
    prompts = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                prompts.append(json.loads(line).get("prompt", ""))
            except Exception:
                pass
    return "\n".join(prompts)


def _get_proc_info(pid: int) -> tuple[int | None, str]:
    try:
        import subprocess
        out = subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "ppid=,comm="],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        parts = out.split(None, 1)
        if len(parts) == 2:
            return int(parts[0]), parts[1]
        elif len(parts) == 1:
            return int(parts[0]), ""
    except Exception:
        pass
    return None, ""


def resolve_agent_pid(payload: dict) -> int | None:
    """Resolve the PID of the actual agent process to observe (never self PID).

    Checks in priority order:
    1. Explicit PID in payload ('agent_pid', 'pid', 'claude_pid', 'process_id')
    2. Explicit PID in environment ('CLAUDE_CODE_PID', 'CLAUDE_PID', 'AGENT_PID', 'INTENT_GUARD_TARGET_PID')
    3. Process tree climbing from os.getppid():
       Hooks are spawned as child processes by Claude Code (or via a shell wrapper like /bin/sh -c).
       If parent is a shell (/bin/sh, /bin/bash, /bin/zsh), climb to grandparent to locate the actual
       calling agent process (Node.js / Claude Code runtime).
    """
    for key in ("agent_pid", "pid", "claude_pid", "process_id"):
        val = payload.get(key)
        if val is not None:
            try:
                p = int(val)
                if p > 1 and p != os.getpid():
                    return p
            except (ValueError, TypeError):
                pass

    for env_key in ("CLAUDE_CODE_PID", "CLAUDE_PID", "AGENT_PID", "INTENT_GUARD_TARGET_PID"):
        val = os.environ.get(env_key)
        if val:
            try:
                p = int(val)
                if p > 1 and p != os.getpid():
                    return p
            except (ValueError, TypeError):
                pass

    try:
        current_pid = os.getppid()
        for _ in range(3):
            if current_pid <= 1 or current_pid == os.getpid():
                break
            ppid, comm = _get_proc_info(current_pid)
            base_comm = Path(comm).name.lower()
            if base_comm in ("sh", "bash", "zsh", "dash"):
                if ppid and ppid > 1 and ppid != os.getpid():
                    current_pid = ppid
                else:
                    return current_pid
            else:
                return current_pid
        return current_pid if (current_pid > 1 and current_pid != os.getpid()) else None
    except Exception:
        return None


def main() -> int:
    try:
        raw_text = sys.stdin.read()
        payload = json.loads(raw_text) if raw_text.strip() else {}
    except Exception:
        return 0

    session_id = str(payload.get("session_id", "unknown-session"))
    trace_path = STATE_DIR / f"{session_id}.trace.jsonl"
    scope_path = STATE_DIR / f"{session_id}.scope.jsonl"

    try:
        from lsa.drift.redaction import append_redacted_raw_log
        append_redacted_raw_log(STATE_DIR, "Stop", payload)
    except Exception:
        pass

    events = load_events(trace_path)
    task_text = load_scope_text(scope_path)
    fp = extract_fingerprint(task_text)
    scope = SessionScope(task_text=task_text, known_paths=fp.authorized_paths)

    if not events:
        trace_path.unlink(missing_ok=True)
        scope_path.unlink(missing_ok=True)
        return 0

    # ── Pass 1: Regex mutation rules ──────────────────────────────────────────
    rule_alerts = MutationComparator().compare(scope, events)

    # ── Pass 2: Semantic LLM review ───────────────────────────────────────────
    settings = _Settings()
    reviewer = SemanticSessionReviewer(
        model=settings.remediation_model,
        preferred_provider=settings.remediation_provider,
    )
    semantic_alerts = reviewer.review(scope, events)
    seen_targets = {a.observed_target for a in rule_alerts}
    all_alerts = rule_alerts + [a for a in semantic_alerts if a.observed_target not in seen_targets]
    all_alerts = sorted(all_alerts, key=lambda a: {"critical": 0, "high": 1, "medium": 2}.get(a.severity, 3))

    # ── Pass 3: Invariant checking ────────────────────────────────────────────
    invariants = load_invariants(session_id)
    invariant_violations = check_invariants(session_id, events, invariants)

    # ── Pass 4: Injection detection ───────────────────────────────────────────
    alert_targets = [a.observed_target for a in all_alerts]
    injection_signals = detect_injection(
        session_id, events, fp.authorized_paths, alert_targets
    )

    # ── Pass 5: Ledger — append entries + check cross-session patterns ────────
    for event in events:
        sev = next(
            (a.severity for a in all_alerts if a.observed_target == event.target),
            "none",
        )
        append_to_ledger(session_id, event, sev)
    ledger_entries = load_ledger()
    ledger_patterns = analyze_ledger(ledger_entries)

    # ── Pass 6: Independent OS Syscall Observation & Discrepancy Detection ───
    # Observes open process file descriptors of the agent process independently of self-reported trace.
    syscall_discrepancies: list[str] = []
    syscall_notice: str | None = None
    try:
        target_pid = resolve_agent_pid(payload)
        if target_pid is None:
            syscall_notice = "Agent process identity could not be resolved from hook payload or process tree; OS descriptor spot-check skipped."
        else:
            from lsa.drift.models import ObservationMode
            os_events, obs_mode = observe_process(target_pid, duration_seconds=0.2)
            if obs_mode == ObservationMode.UNAVAILABLE or sys.platform == "win32":
                syscall_notice = f"Syscall cross-check unavailable on platform '{sys.platform}'. OS process descriptor verification did not run."
                sys.stderr.write(f"[intent-guard notice] {syscall_notice}\n")
            elif os_events:
                self_reported_targets = {e.target for e in events}
                # Identify sensitive files touched at OS level but missing from self-reported trace
                for os_ev in os_events:
                    t = os_ev.target
                    if any(k in t.lower() for k in (".env", "id_rsa", "credentials", "secrets", "passwd")):
                        if t not in self_reported_targets and not any(r in t for r in self_reported_targets):
                            syscall_discrepancies.append(t)
    except Exception:
        pass

    # ── Build report ──────────────────────────────────────────────────────────
    has_findings = any([all_alerts, invariant_violations, injection_signals, ledger_patterns, syscall_discrepancies])
    if has_findings:
        client = build_remediation_client(_Settings())
        placeholder = FunctionIntent(
            name=session_id, module="session", qualname=f"session:{session_id}",
            lineno=0, end_lineno=0,
        )
        lines = [f"# intent-guard session report ({session_id})\n"]

        for alert in all_alerts:
            prompt = (
                f"Task description:\n{task_text}\n\n"
                f"Flagged action: {alert.observed_target}\nSeverity: {alert.severity}\n"
                f"Reason: {alert.reason}\nWrite a short remediation report."
            )
            report = client.analyze(placeholder, alert, prompt)
            lines.append(report.to_markdown())

        if invariant_violations:
            lines.append("## ⚠️ Invariant Violations (Pre-Stated Contracts Broken)\n")
            for v in invariant_violations:
                lines.append(f"- **[{v.severity.upper()}]** `{v.observed_target}` violated: _{v.invariant_description}_\n")

        if injection_signals:
            lines.append("## 🚨 Prompt Injection Signals\n")
            for s in injection_signals:
                lines.append(
                    f"- **[confidence={s.confidence:.0%}]** Agent read `{s.read_target}` "
                    f"then performed out-of-scope action on `{s.triggered_action}`. "
                    f"Possible prompt injection via file content.\n"
                )

        if ledger_patterns:
            lines.append("## 📊 Cross-Session Behavioral Patterns\n")
            for p in ledger_patterns:
                lines.append(f"- **[{p.severity.upper()}] {p.pattern}**: {p.description}\n")

        if syscall_discrepancies:
            lines.append("## 🛡️ Telemetry Discrepancy (OS Process Spot-Check Alert)\n")
            lines.append(
                "> [!NOTE]\n"
                "> Observation Window Note: This pass evaluates an OS-level open file descriptor spot-check "
                "at session Stop time. Discrepancies indicate resources accessed by the agent process "
                "that were omitted from self-reported tool calls.\n\n"
            )
            for disc in syscall_discrepancies:
                lines.append(
                    f"- **[CRITICAL]** Process had open handle to `{disc}` at OS level, "
                    f"but this resource was NOT self-reported in tool calls. Potential hook bypass attempt.\n"
                )

        if syscall_notice:
            lines.append("## ℹ️ OS Telemetry Notice\n")
            lines.append(f"> [!WARNING]\n> {syscall_notice}\n\n")

        report_dir = STATE_DIR / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{session_id}.md"
        report_path.write_text("\n".join(lines), encoding="utf-8")

        top_sev = (
            "critical" if (syscall_discrepancies or any(a.severity == "critical" for a in all_alerts) or invariant_violations)
            else (all_alerts[0].severity if all_alerts else "high")
        )
        extras = []
        if invariant_violations:
            extras.append(f"{len(invariant_violations)} invariant violation(s)")
        if injection_signals:
            extras.append(f"{len(injection_signals)} injection signal(s)")
        if ledger_patterns:
            extras.append(f"{len(ledger_patterns)} cross-session pattern(s)")
        if syscall_discrepancies:
            extras.append(f"{len(syscall_discrepancies)} OS telemetry discrepancy alert(s)")
        extra_str = (", " + ", ".join(extras)) if extras else ""
        summary = (
            f"intent-guard flagged {len(all_alerts)} action(s){extra_str} this session "
            f"(highest severity: {top_sev}). Full report: {report_path}"
        )
        print(json.dumps({"systemMessage": summary}))

        # ── SIEM Webhook Export (L2.2) ────────────────────────────────────────
        webhook_url = os.environ.get("LSA_SIEM_WEBHOOK_URL")
        if webhook_url:
            try:
                import urllib.request
                from lsa.drift.redaction import redact_json_obj
                webhook_payload = {
                    "event_type": "intent_guard_findings",
                    "session_id": session_id,
                    "organization_name": os.environ.get("LSA_ORG", "default"),
                    "highest_severity": top_sev,
                    "alerts_count": len(all_alerts),
                    "invariant_violations_count": len(invariant_violations),
                    "injection_signals_count": len(injection_signals),
                    "syscall_discrepancies_count": len(syscall_discrepancies),
                    "alerts": [
                        {
                            "severity": a.severity,
                            "target": a.observed_target,
                            "reason": getattr(a, "reason", getattr(a, "explanation", "")),
                        }
                        for a in all_alerts
                    ],
                }
                redacted_webhook_payload = redact_json_obj(webhook_payload)
                req_bytes = json.dumps(redacted_webhook_payload).encode("utf-8")
                req = urllib.request.Request(
                    webhook_url,
                    data=req_bytes,
                    headers={"Content-Type": "application/json", "User-Agent": "intent-guard/siem-exporter/0.2.0"},
                )
                urllib.request.urlopen(req, timeout=3.0)
            except Exception as ex:
                sys.stderr.write(f"[intent-guard SIEM export error]: {ex}\n")

    # ── Retention Policy (P1 Item 8) ──────────────────────────────────────────
    # If INTENT_GUARD_RETAIN_EVENTS=true, retain raw traces, scopes, and sigs
    # for audit and compliance instead of unconditionally wiping evidence.
    retain_evidence = os.environ.get("INTENT_GUARD_RETAIN_EVENTS", "false").lower() in ("true", "1", "yes")
    if retain_evidence:
        archive_dir = STATE_DIR / "archive"
        archive_dir.mkdir(exist_ok=True)
        if trace_path.exists():
            trace_path.rename(archive_dir / f"{session_id}.trace.jsonl")
        if scope_path.exists():
            scope_path.rename(archive_dir / f"{session_id}.scope.jsonl")
        sig_file = STATE_DIR / f"{session_id}.sig"
        if sig_file.exists():
            sig_file.rename(archive_dir / f"{session_id}.sig")
    else:
        trace_path.unlink(missing_ok=True)
        scope_path.unlink(missing_ok=True)
        (STATE_DIR / f"{session_id}.sig").unlink(missing_ok=True)

    (STATE_DIR / f"{session_id}.invariants.json").unlink(missing_ok=True)
    (STATE_DIR / f"{session_id}.pretool.jsonl").unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
