from __future__ import annotations

import re
from dataclasses import dataclass, field

from lsa.drift.models import DriftAlert, ObservedEvent

# Irreversible or wide-blast-radius actions. These fire even on a session
# with no declared scope at all, because "delete production data" is not a
# risk that should require the human to have pre-declared it as off-limits.
DESTRUCTIVE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("filesystem-wide delete", re.compile(r"\brm\s+-[a-z]*r[a-z]*f\b|\brm\s+-[a-z]*f[a-z]*r\b", re.I)),
    ("force push", re.compile(r"\bgit\s+push\b.*(--force|-f)\b", re.I)),
    ("sql destructive", re.compile(r"\b(drop\s+table|drop\s+database|truncate\s+table|delete\s+from\s+\S+)", re.I)),
    ("migration reset", re.compile(r"\bmigrate\s+(diff|reset)\b.*shadow", re.I)),
    ("permissive chmod", re.compile(r"\bchmod\s+(-R\s+)?777\b", re.I)),
]

# Plain file-deletion / mutation operations (F2).
# Kept separate from critical destructive operations so they stay unflagged
# under unconstrained sessions, but are strictly flagged when a read-only
# or negative modification constraint exists.
PLAIN_DELETION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("plain file delete", re.compile(r"\b(rm(\s+-[a-z0-9]*)?\s+|unlink\s+|os\.remove\b|os\.unlink\b|del\s+|Remove-Item\b)", re.I)),
]

# Worth a note, not inherently destructive -- and suppressed entirely when
# the target is something the human's own task already named, since touching
# a credential file the task is literally about is expected, not drift.
SENSITIVE_TOUCH_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("credential file touch", re.compile(r"\.env(\.\w+)?$|\bid_rsa\b|\bcredentials\.json\b", re.I)),
]

# Phrases that, if present in the human's own task description, establish an
# explicit negative constraint. If a later action's target/command matches
# one of these, that is not "unexpected" -- it is a direct contradiction of
# something the human already said. This is the exact shape of the PocketOS
# and Replit incidents: the agent had the rule, and broke it anyway.
CONSTRAINT_PHRASES: list[re.Pattern[str]] = [
    re.compile(r"\b(do not|don't|never)\b.{0,40}\b(delete|drop|truncate|wipe|remove|modify|change|alter|edit|touch)\b", re.I),
    re.compile(r"\bcode freeze\b", re.I),
    re.compile(r"\bread[- ]only\b", re.I),
    re.compile(r"\bwithout (my )?(explicit )?approval\b", re.I),
    re.compile(r"\bdo not touch (prod|production)\b", re.I),
    re.compile(r"\bnever run destructive\b", re.I),
    re.compile(r"\bno\s+writes?\b", re.I),
    re.compile(r"\bno\s+modifications?\b", re.I),
    re.compile(r"\bonly\s+read\b", re.I),
]

_READ_ONLY_SCOPE_RE = re.compile(
    r"\bread[- ]only\b|\bnever\s+modify\b|\bdo\s+not\s+(?:modify|change|edit|write|alter|touch)\b|\bdon'?t\s+(?:modify|change|edit|write|alter|touch)\b|\bno\s+writes?\b|\bno\s+modifications?\b|\bonly\s+read\b|\bjust\s+read\b|\bdo\s+not\s+touch\s+anything\b|\bnever\s+touch\s+anything\b",
    re.I,
)


@dataclass(slots=True)
class SessionScope:
    """What the human actually declared, in their own words, at the start
    of (or during) the session. Deliberately text-based rather than a
    structured policy file -- v1 works with whatever the human already
    typed, instead of asking them to maintain a second source of truth."""

    task_text: str
    known_paths: list[str] = field(default_factory=list)

    @property
    def declared_constraints(self) -> list[str]:
        return [m.group(0) for pattern in CONSTRAINT_PHRASES for m in pattern.finditer(self.task_text)]

    @property
    def is_read_only(self) -> bool:
        return bool(_READ_ONLY_SCOPE_RE.search(self.task_text))


class MutationComparator:
    """Compares observed file/shell/MCP actions in a session against the
    scope the human actually declared. Complements DriftComparator, which
    only looks at event_type == 'network'. This looks at event_type ==
    'mutation'."""

    def compare(self, scope: SessionScope, events: list[ObservedEvent]) -> list[DriftAlert]:
        alerts: list[DriftAlert] = []
        constraints = scope.declared_constraints

        for event in events:
            if event.event_type != "mutation":
                continue

            command = event.metadata.get("command", "")
            target = event.target
            haystack = f"{command} {target}"
            in_declared_scope = any(path and path in target for path in scope.known_paths)

            destructive_hit = next(
                (label for label, pattern in DESTRUCTIVE_PATTERNS if pattern.search(haystack)),
                None,
            )
            sensitive_hit = next(
                (label for label, pattern in SENSITIVE_TOUCH_PATTERNS if pattern.search(haystack)),
                None,
            )

            plain_delete_hit = next(
                (label for label, pattern in PLAIN_DELETION_PATTERNS if pattern.search(haystack)),
                None,
            )

            if destructive_hit is not None:
                contradicts_stated_rule = bool(constraints)
                success = event.metadata.get("success", True)
                exit_code = event.metadata.get("exit_code", 0)

                if success is False:
                    severity = "high" if contradicts_stated_rule else "medium"
                    status_note = f" (execution failed with exit_code={exit_code}; attempted destructive action)"
                else:
                    severity = "critical" if contradicts_stated_rule else "high"
                    status_note = ""

                alerts.append(
                    DriftAlert(
                        function=event.function,
                        observed_target=target,
                        expected_targets=list(scope.known_paths),
                        severity=severity,
                        reason=(
                            f"Action matches a destructive pattern ('{destructive_hit}')"
                            + status_note
                            + (
                                f" and the session's own task description contains an explicit "
                                f"constraint that this appears to violate: \"{constraints[0]}\"."
                                if contradicts_stated_rule
                                else ", which carries irreversible risk regardless of stated scope."
                            )
                        ),
                    )
                )
            elif plain_delete_hit is not None and (scope.is_read_only or bool(constraints)):
                # Plain deletion under a read-only or constrained task is a direct violation
                constraint_ref = constraints[0] if constraints else "read-only"
                alerts.append(
                    DriftAlert(
                        function=event.function,
                        observed_target=target,
                        expected_targets=list(scope.known_paths),
                        severity="high",
                        reason=(
                            f"Action performs a mutating file deletion ('{plain_delete_hit}'), "
                            f"which violates the session's explicit read-only constraint: \"{constraint_ref}\"."
                        ),
                    )
                )
            elif sensitive_hit is not None and not in_declared_scope:
                alerts.append(
                    DriftAlert(
                        function=event.function,
                        observed_target=target,
                        expected_targets=list(scope.known_paths),
                        severity="medium",
                        reason=(
                            f"Touched a sensitive file ('{sensitive_hit}') that wasn't named "
                            f"anywhere in the task description."
                        ),
                    )
                )
            elif not in_declared_scope and scope.known_paths:
                alerts.append(
                    DriftAlert(
                        function=event.function,
                        observed_target=target,
                        expected_targets=list(scope.known_paths),
                        severity="medium",
                        reason="Target was not mentioned anywhere in the task description or prior scope.",
                    )
                )

        return alerts
