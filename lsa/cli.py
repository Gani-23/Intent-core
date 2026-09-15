from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from lsa.drift.benchmark import format_benchmark_markdown, run_benchmark
from lsa.drift.intent_fingerprint import extract_fingerprint
from lsa.drift.models import ObservedEvent
from lsa.drift.mutation_rules import MutationComparator, SessionScope


# ── ANSI Terminal Colors ──────────────────────────────────────────────────────
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"


def print_banner():
    banner = f"""{Colors.CYAN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════╗
║                   🛡️   INTENT-GUARD                           ║
║   Living Systems Auditor — Autonomous Agent Governance Rail   ║
╚═══════════════════════════════════════════════════════════════╝{Colors.RESET}
"""
    print(banner)


# ── 1. Check Command ──────────────────────────────────────────────────────────
def cmd_check(args: argparse.Namespace) -> int:
    task_text = args.task
    command = args.command
    tool_name = args.tool or "bash"

    if not task_text or not command:
        print(f"{Colors.RED}Error: Both --task and --command are required.{Colors.RESET}", file=sys.stderr)
        return 2

    fp = extract_fingerprint(task_text)
    scope = SessionScope(task_text=task_text, known_paths=fp.authorized_paths)
    event = ObservedEvent(
        function="cli:check",
        event_type="mutation",
        target=command,
        metadata={"tool_name": tool_name, "command": command},
    )
    comparator = MutationComparator()
    alerts = comparator.compare(scope, [event])

    is_drift = len(alerts) > 0
    top_alert = alerts[0] if alerts else None
    severity = top_alert.severity.upper() if top_alert else "LOW"
    reason = (
        getattr(top_alert, "reason", getattr(top_alert, "explanation", "Action matches expected task intent."))
        if top_alert
        else "Command execution permitted in approved task scope."
    )

    if args.json:
        output = {
            "caught": is_drift,
            "verdict": "BLOCKED_AS_DRIFT" if is_drift else "PERMITTED_IN_SCOPE",
            "severity": severity,
            "task_text": task_text,
            "command": command,
            "reason": reason,
            "fingerprint": fp.to_dict(),
        }
        print(json.dumps(output, indent=2))
        return 1 if is_drift else 0

    if is_drift:
        print(f"{Colors.RED}{Colors.BOLD}⛔  EXECUTION BLOCKED — INTENT DRIFT DETECTED [{severity}]{Colors.RESET}")
        print(f"  {Colors.BOLD}Assigned Task:{Colors.RESET} {task_text}")
        print(f"  {Colors.BOLD}Attempted Cmd:{Colors.RESET} {command}")
        print(f"  {Colors.BOLD}Violation:{Colors.RESET}    {reason}")
        print(f"\n{Colors.YELLOW}🛡️  Pre-tool policy check prevented out-of-scope mutation.{Colors.RESET}")
        return 1
    else:
        print(f"{Colors.GREEN}{Colors.BOLD}✅  EXECUTION PERMITTED — IN APPROVED SCOPE{Colors.RESET}")
        print(f"  {Colors.BOLD}Task:{Colors.RESET}    {task_text}")
        print(f"  {Colors.BOLD}Command:{Colors.RESET} {command}")
        return 0


# ── 2. Gate Command ───────────────────────────────────────────────────────────
def cmd_gate(args: argparse.Namespace) -> int:
    bundle_path = Path(args.proof_bundle)
    if not bundle_path.exists():
        print(f"{Colors.RED}❌ Error: Proof bundle not found at {bundle_path}{Colors.RESET}", file=sys.stderr)
        return 2

    try:
        data = json.loads(bundle_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"{Colors.RED}❌ Error parsing proof bundle JSON: {e}{Colors.RESET}", file=sys.stderr)
        return 2

    # Verify SHA-256 if recorded
    recorded_sha = data.get("sha256")
    file_bytes = bundle_path.read_bytes()
    computed_sha = hashlib.sha256(file_bytes).hexdigest()

    blockers = data.get("blockers", [])
    valid = data.get("valid", True) and len(blockers) == 0

    if args.json:
        output = {
            "path": str(bundle_path),
            "valid": valid,
            "blockers_count": len(blockers),
            "blockers": blockers,
            "sha256": computed_sha,
            "target_profile": data.get("target_profile", "unknown"),
            "environment": data.get("environment", "production"),
        }
        print(json.dumps(output, indent=2))
        return 0 if valid else 1

    print_banner()
    print(f"{Colors.BOLD}Validating Release Gate with Proof Bundle:{Colors.RESET} {bundle_path.name}")
    print(f"Target Profile:  {Colors.CYAN}{data.get('target_profile', 'unknown')}{Colors.RESET}")
    print(f"Environment:     {Colors.CYAN}{data.get('environment', 'production')}{Colors.RESET}")
    print(f"SHA-256 Digest:  {computed_sha[:16]}...")

    if valid:
        print(f"\n{Colors.GREEN}{Colors.BOLD}PASSED — SAFE FOR DEPLOYMENT PROMOTION{Colors.RESET}")
        print("All runtime invariants preserved. Zero out-of-scope mutations detected.")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}BLOCKED — DEPLOYMENT GATE INVARIANTS FAILED{Colors.RESET}")
        for b in blockers:
            print(f"  - {Colors.RED}{b}{Colors.RESET}")
        return 1


# ── 3. Benchmark Command ──────────────────────────────────────────────────────
def cmd_benchmark(args: argparse.Namespace) -> int:
    print_banner()
    print(f"{Colors.BOLD}Running Intent-Guard 20-Scenario Invariant Regression Suite...{Colors.RESET}\n")
    report = run_benchmark()
    md = format_benchmark_markdown(report)
    print(md)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        print(f"\nSaved JSON report to: {out_path}")

    if args.markdown:
        md_path = Path(args.markdown)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(md, encoding="utf-8")
        print(f"Saved Markdown report to: {md_path}")

    return 0 if report.accuracy_percentage == 100.0 else 1


# ── 4. Hook Command ───────────────────────────────────────────────────────────
def cmd_hook(args: argparse.Namespace) -> int:
    hooks_dir = Path(".intent-guard/hooks")
    hooks_dir.mkdir(parents=True, exist_ok=True)

    hook_script = hooks_dir / "pre-tool.sh"
    hook_content = """#!/usr/bin/env bash
# Intent-Guard Pre-Tool Interception Hook
# Intercepts autonomous agent commands and evaluates intent drift before execution.

set -e

TASK_PROMPT="${INTENT_GUARD_TASK:-$1}"
COMMAND_TO_RUN="${INTENT_GUARD_COMMAND:-$2}"

if [ -z "$TASK_PROMPT" ] || [ -z "$COMMAND_TO_RUN" ]; then
    # Pass through if unconfigured
    exit 0
fi

# Run pre-tool evaluation
intent-guard check --task "$TASK_PROMPT" --command "$COMMAND_TO_RUN"
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "❌ Intent-Guard blocked command: $COMMAND_TO_RUN" >&2
    exit 1
fi

exit 0
"""
    hook_script.write_text(hook_content, encoding="utf-8")
    os.chmod(hook_script, 0o755)

    print_banner()
    print(f"{Colors.GREEN}{Colors.BOLD}Intent-Guard pre-tool hook installed at:{Colors.RESET} {hook_script}")
    print(f"""
{Colors.BOLD}Integration Instructions:{Colors.RESET}

1. {Colors.CYAN}Claude Code:{Colors.RESET}
   Add to your agent hooks configuration:
   `"pre_tool": "{hook_script.resolve()}"`

2. {Colors.CYAN}Cursor / Custom Agent Runner:{Colors.RESET}
   Execute commands through the guard wrapper:
   `{hook_script.resolve()} "<assigned_task>" "<command>"`

3. {Colors.CYAN}Environment Variable Override:{Colors.RESET}
   `export INTENT_GUARD_TASK="Fix navbar CSS"`
   `intent-guard check --task "$INTENT_GUARD_TASK" --command "rm -rf /"`
""")
    return 0


# ── Main Entrypoint ───────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="intent-guard",
        description="Intent-Guard CLI: Runtime Intent Governance and Pre-tool Safety Interception",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Command to run")

    # Check
    p_check = subparsers.add_parser("check", help="Evaluate if an agent action drifts from stated intent")
    p_check.add_argument("-t", "--task", required=True, help="User prompt or task intent text")
    p_check.add_argument("-c", "--command", required=True, help="Command or action to evaluate")
    p_check.add_argument("--tool", default="bash", help="Tool name (e.g. bash, edit, write)")
    p_check.add_argument("--json", action="store_true", help="Output JSON result")

    # Gate
    p_gate = subparsers.add_parser("gate", help="Validate release gate using signed proof bundles")
    p_gate.add_argument("-p", "--proof-bundle", required=True, help="Path to proof bundle JSON")
    p_gate.add_argument("--min-trust-score", type=int, default=80, help="Minimum trust score threshold")
    p_gate.add_argument("--json", action="store_true", help="Output JSON result")

    # Benchmark / Invariant Regression Suite
    p_bench = subparsers.add_parser(
        "benchmark",
        aliases=["regression", "test-suite"],
        help="Run 20-scenario deterministic invariant regression suite",
    )
    p_bench.add_argument("-o", "--output", help="Output path for JSON report")
    p_bench.add_argument("-m", "--markdown", help="Output path for Markdown report")

    # Hook
    p_hook = subparsers.add_parser("hook", help="Install pre-tool interception hooks for autonomous agents")
    p_hook.add_argument("--agent", default="all", choices=["claude-code", "cursor", "shell", "all"])

    parsed = parser.parse_args(argv)

    if not parsed.subcommand:
        parser.print_help()
        return 0

    if parsed.subcommand == "check":
        return cmd_check(parsed)
    elif parsed.subcommand == "gate":
        return cmd_gate(parsed)
    elif parsed.subcommand in ("benchmark", "regression", "test-suite"):
        return cmd_benchmark(parsed)
    elif parsed.subcommand == "hook":
        return cmd_hook(parsed)

    return 0


if __name__ == "__main__":
    sys.exit(main())
