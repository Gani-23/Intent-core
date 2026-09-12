"""Static git diff auditor for pull requests (Option B).

Analyzes proposed code changes in git diffs against declared PR intent.
Unlike MutationComparator (which evaluates executed actions in live agent sessions),
StaticDiffAuditor analyzes proposed changes statically:
1. Intent scope drift: detects undeclared modifications to sensitive files (.env, secrets, CI workflows).
2. Executable surface risk: inspects ADDED lines in executable files (scripts, workflows, Dockerfiles)
   for dangerous/destructive commands, while avoiding false positives on documentation, comments,
   test fixtures, or security pattern definitions in general source code.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePath
from typing import Sequence

# Sensitive file patterns that should not be touched unless explicitly declared in PR intent
SENSITIVE_PATH_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("secret-env", re.compile(r"(^|/)\.env(\.[a-zA-Z0-9_-]+)?$", re.IGNORECASE), "critical"),
    ("private-key", re.compile(r"(^|/)(id_rsa|id_ed25519|.*\.pem|.*\.key)$", re.IGNORECASE), "critical"),
    ("credential-store", re.compile(r"(^|/)(.*credentials.*|.*secret.*|.*token.*)\.(json|ya?ml|txt)$", re.IGNORECASE), "critical"),
    ("ci-workflow", re.compile(r"^\.github/workflows/.*\.ya?ml$", re.IGNORECASE), "high"),
]

# File types that directly execute shell commands
EXECUTABLE_EXTENSIONS = {".sh", ".bash", ".zsh", ".ksh"}
EXECUTABLE_FILENAMES = {"Dockerfile", "Containerfile", "Makefile", "GNUmakefile", "Justfile"}

# Destructive command patterns for executable surfaces
DESTRUCTIVE_COMMAND_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("filesystem-wide delete", re.compile(r"rm\s+-(?:r[fv]|fr|r|f)\s+(?:/|~)(?:\s|$|;|\&|\|)", re.IGNORECASE)),
    ("workspace-wide delete", re.compile(r"rm\s+-(?:r[fv]|fr|r|f)\s+(?:\$GITHUB_WORKSPACE|\$\{GITHUB_WORKSPACE\}|\$HOME|\$\{HOME\}|\.\.?)(?:\s|$|;|\&|\|)", re.IGNORECASE)),
    ("no-preserve-root delete", re.compile(r"rm\s+.*--no-preserve-root", re.IGNORECASE)),
    ("filesystem wipe", re.compile(r"mkfs(?:\.[a-z0-9]+)?\s+", re.IGNORECASE)),
    ("raw block device overwrite", re.compile(r"dd\s+if=/dev/(?:zero|urandom)\s+of=/dev/", re.IGNORECASE)),
    ("unverified remote script execution", re.compile(r"(?:curl|wget)\s+[^|\r\n]+\|\s*(?:ba|z)?sh\b", re.IGNORECASE)),
    ("fork bomb", re.compile(r":\(\)\s*\{\s*:\|:&\s*\};:", re.IGNORECASE)),
    ("mass process kill", re.compile(r"kill\s+-9\s+-1\b", re.IGNORECASE)),
]


@dataclass(frozen=True)
class DiffFinding:
    target: str
    severity: str  # "critical", "high", "medium", "low"
    reason: str


class StaticDiffAuditor:
    """Static auditor evaluating proposed git diff changes against declared intent."""

    def is_executable_surface(self, filename: str) -> bool:
        """Determine if a file represents an executable surface where lines run directly as shell commands."""
        path = PurePath(filename)
        if path.suffix.lower() in EXECUTABLE_EXTENSIONS:
            return True
        if path.name in EXECUTABLE_FILENAMES or path.suffix.lower() == ".dockerfile":
            return True
        # GitHub Actions workflows contain executable run: steps
        if str(path).startswith(".github/workflows/") and path.suffix.lower() in (".yml", ".yaml"):
            return True
        return False

    def extract_added_lines(self, patch: str) -> list[str]:
        """Extract only newly added lines from unified diff patch (+ prefix, skipping +++ header)."""
        added = []
        for line in patch.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                added.append(line[1:].strip())
        return added

    def audit_pr(
        self,
        title: str,
        body: str,
        files: Sequence[dict[str, str]],
    ) -> list[DiffFinding]:
        """Audit PR files and patches against declared intent and security rules."""
        findings: list[DiffFinding] = []
        task_description = f"{title}\n{body}".strip()
        declared_paths = set(re.findall(r"[\w./-]+\.[a-zA-Z0-9]+", task_description))

        for f in files:
            filename = f.get("filename", "")
            patch = f.get("patch", "")
            status = f.get("status", "modified")

            if not filename:
                continue

            # 1. Scope & Sensitive Path Inspection
            in_declared_intent = (
                filename in declared_paths
                or any(p in filename or filename in p for p in declared_paths)
                or filename in task_description
            )

            for label, pattern, severity in SENSITIVE_PATH_PATTERNS:
                if label == "secret-env" and "example" in filename.lower():
                    continue

                if pattern.search(filename) and not in_declared_intent:
                    findings.append(
                        DiffFinding(
                            target=filename,
                            severity=severity,
                            reason=f"Proposed change touches sensitive path '{filename}' without explicit declaration in PR intent.",
                        )
                    )
                    break

            # 2. Executable Surface Command Inspection
            if self.is_executable_surface(filename):
                added_lines = self.extract_added_lines(patch)
                for line in added_lines:
                    cmd_candidate = line
                    if line.startswith("run:"):
                        cmd_candidate = line[4:].strip()

                    for label, cmd_pattern in DESTRUCTIVE_COMMAND_PATTERNS:
                        if cmd_pattern.search(cmd_candidate):
                            findings.append(
                                DiffFinding(
                                    target=filename,
                                    severity="critical" if "delete" in label or "wipe" in label else "high",
                                    reason=(
                                        f"Proposed change in executable surface introduces destructive command "
                                        f"('{label}'): '{cmd_candidate[:120]}'"
                                    ),
                                )
                            )
                            break

        return findings
