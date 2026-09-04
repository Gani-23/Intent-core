# intent-guard

A Claude Code plugin that checks whether what an agent actually *did* in a
session matches what you actually *asked* it to do — and flags the gap
before it becomes an incident.

Built from the detection engine in [intent-core/LSA](https://github.com/Gani-23/Intent-core):
`lsa/core`, `lsa/ingest`, `lsa/drift`, `lsa/remediation` are copied over
close to as-is. Everything in `hooks/` and `lsa/drift/mutation_rules.py` is
new, built to plug that engine into Claude Code's hook system instead of
eBPF network tracing.

## Why this exists

Existing agent-safety tooling checks identity/credentials (who the agent
is), code content (does the code look vulnerable), or output quality (was
the reasoning good). None of them ask the one question that actually
mattered in the real 2026 incidents this is modeled on — Replit deleting a
production DB during a code freeze, a Cursor agent deleting a database via
an over-scoped token in nine seconds, a routine-looking Prisma command
wiping tables via a shadow-database reset: **did the whole set of things the
agent did still match what was asked, in aggregate** — not what it was
credentialed to touch, not whether the command matched a blocklist pattern.

## Detection architecture (two passes)

1. **Regex pass** (`mutation_rules.py`, `MutationComparator`) — fast, free, always on. Catches known-bad syntax (`rm -rf`, `DROP TABLE`, `--force` push) and direct contradictions of something the human explicitly said not to do. Zero API cost, zero latency.
2. **Semantic pass** (`semantic_review.py`, `SemanticSessionReviewer`) — reads the session (task description + every action taken) and judges fit as a human reviewer would, catching things no keyword list ever will. Example proven in `examples/demo_pocketos_scenario.py`: a task says "read-only audit, do not modify records" and the session runs `UPDATE users SET verified=true WHERE id=445` — zero regex alerts, because nothing about `UPDATE ... WHERE` looks dangerous.

Pass 2 features a robust **multi-provider failsafe cascade**:
- **Anthropic**: Uses `ANTHROPIC_API_KEY` (Claude).
- **OpenAI**: Fails over to `OPENAI_API_KEY` (e.g. `gpt-4o-mini`).
- **Gemini**: Fails over to `GEMINI_API_KEY` or `GOOGLE_API_KEY` (`gemini-2.5-flash`).
- **Antigravity**: Local bridge via `agentapi new-conversation` on Mac Mini/Apple Silicon — runs 100% locally with zero cloud API keys needed (verified in ~2.5s).
- **Deterministic Failsafe**: If all tokens are absent and all network providers fail, evaluates explicit task prohibitions against mutation statements (`UPDATE`, `INSERT`, `DELETE`) without crashing. Zero external pip packages (pure stdlib).

## What's actually proven vs. what's a first pass

**Proven, tested end-to-end in this sandbox** (see `examples/`):
- The comparator correctly flags a destructive, task-contradicting action
  (recreates the Prisma/PocketOS incident shape) and does *not* flag a
  benign, in-scope edit — verified by running it, not just reading it.
- The three hook scripts run correctly against simulated Claude Code stdin
  end-to-end: capture → compare → report → rotate.
- Every file compiles clean. Zero external dependencies — pure stdlib, so
  there's nothing to `pip install` for the hooks themselves.

**A first pass, not a finished product:**
- `CONSTRAINT_PHRASES` and `DESTRUCTIVE_PATTERNS` in `mutation_rules.py` are
  a starting set of regexes, not a validated list. Expect false negatives
  (patterns not yet covered) and occasional false positives — the first
  version already had one (an in-scope `.env` edit flagged as critical; see
  git history in the conversation this was built in for how it was caught
  and fixed). Treat every alert as a hypothesis to sanity-check, not a
  verdict, until this has run against real sessions.
- The field names in `hooks/*.py` (`session_id`, `prompt`, `tool_name`,
  `tool_input`) were verified against the actual Claude Code v2.1.259
  binary (`strings` on the compiled release, not just the docs site) — all
  four appear exactly as used here. **Still unverified:** the exact JSON
  envelope shape (nesting) and real runtime behavior, which need an
  authenticated session on real hardware to confirm. Known gap found during
  this verification: `tool_response` is a real field this doesn't read yet
  — right now a Bash command is logged as having run, not whether it
  succeeded, which matters for severity.
- No blocking yet — hooks only observe and report after the fact (exit code
  0 always). Turning flagged actions into an actual `PreToolUse` deny is a
  natural v2, deliberately not v1: shipping observe-only first means
  adopting this costs nothing and can't break anyone's existing flow.
- The network-destination side of the original engine (`trace_parser.py`,
  `ebpf_observer.py`, `function_resolution.py`, `destination_resolution.py`)
  is carried over but not wired into the hooks path. It's a legitimate
  second signal (catches an agent quietly calling an undeclared host) for a
  later "deep verification" tier — not required for the MVP.

## Setup

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # optional — falls back to a
                                        # deterministic rule-based report
                                        # if unset, never crashes silently
python3 examples/demo_pocketos_scenario.py   # run this first
```

To actually install as a Claude Code plugin, point `CLAUDE_PLUGIN_ROOT` at
this directory and register `hooks/hooks.json` per the plugin docs — this
part is untested against the real Claude Code runtime and is the next thing
to verify.

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
