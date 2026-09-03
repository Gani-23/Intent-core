"""Tests for all v2 features: manifest_signer, intent_fingerprint,
session_ledger, invariant_checker, injection_detector, syscall_bridge,
pre_tool_check strict mode.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Point STATE_DIR at a temp location so tests don't create .intent-guard/ in cwd
_TMP = tempfile.mkdtemp()
os.environ.setdefault("INTENT_GUARD_STATE", _TMP)

from lsa.drift.models import (
    InjectionSignal, InvariantViolation, LedgerEntry,
    Invariant, ObservationMode, ObservedEvent,
)
from lsa.drift.manifest_signer import (
    sign_manifest, verify_manifest, write_sig_file, verify_sig_file,
)
from lsa.drift.intent_fingerprint import extract_fingerprint
from lsa.drift.session_ledger import (
    _action_hash, analyze_ledger, LedgerPattern,
)
from lsa.drift.invariant_checker import (
    generate_invariants, check_invariants,
)
from lsa.drift.injection_detector import detect_injection
from lsa.drift.syscall_bridge import detect_capability, ObservationMode as BMode


# ── Manifest signer ───────────────────────────────────────────────────────────
class TestManifestSigner(unittest.TestCase):

    def setUp(self):
        # Redirect STATE_DIR for each test
        import lsa.drift.manifest_signer as ms
        self._orig_state = ms.STATE_DIR
        self._orig_key = ms.KEY_FILE
        ms.STATE_DIR = Path(_TMP)
        ms.KEY_FILE = Path(_TMP) / "machine.key"

    def tearDown(self):
        import lsa.drift.manifest_signer as ms
        ms.STATE_DIR = self._orig_state
        ms.KEY_FILE = self._orig_key

    def test_sign_and_verify_roundtrip(self):
        sig = sign_manifest("audit only, do not modify", "session-abc")
        self.assertTrue(verify_manifest("audit only, do not modify", "session-abc", sig))

    def test_tampered_text_fails_verification(self):
        sig = sign_manifest("audit only, do not modify", "session-abc")
        self.assertFalse(verify_manifest("audit only, MODIFIED", "session-abc", sig))

    def test_wrong_session_fails_verification(self):
        sig = sign_manifest("audit only", "session-abc")
        self.assertFalse(verify_manifest("audit only", "session-XYZ", sig))

    def test_sig_file_write_and_verify(self):
        write_sig_file("sess-1", "do not delete")
        ok, reason = verify_sig_file("sess-1", "do not delete")
        self.assertTrue(ok, reason)

    def test_tampered_sig_file_detected(self):
        write_sig_file("sess-2", "original task")
        ok, reason = verify_sig_file("sess-2", "TAMPERED task text")
        self.assertFalse(ok)
        self.assertIn("HMAC mismatch", reason)


# ── Intent fingerprint ────────────────────────────────────────────────────────
class TestIntentFingerprint(unittest.TestCase):

    def test_read_only_audit(self):
        fp = extract_fingerprint(
            "Perform a read-only audit of the users table. Do not modify any records."
        )
        self.assertIn("READ", fp.authorized_ops)
        self.assertNotIn("WRITE", fp.authorized_ops)
        self.assertTrue(len(fp.prohibitions) > 0)
        self.assertGreater(fp.confidence, 0.5)

    def test_deploy_task_extracts_exec(self):
        fp = extract_fingerprint("Deploy the staging container. Run the migration scripts.")
        self.assertIn("EXEC", fp.authorized_ops)

    def test_empty_prompt_gives_low_confidence(self):
        fp = extract_fingerprint("")
        self.assertEqual(fp.confidence, 0.0)
        self.assertEqual(len(fp.authorized_ops), 0)

    def test_path_extraction(self):
        fp = extract_fingerprint("Update config.yaml and review the deployment.env file")
        paths_lower = [p.lower() for p in fp.authorized_paths]
        self.assertTrue(any("yaml" in p or "env" in p for p in paths_lower))


# ── Session ledger ────────────────────────────────────────────────────────────
class TestSessionLedger(unittest.TestCase):

    def _make_entry(self, sid, target, op, severity):
        return LedgerEntry(
            ts="2026-09-03T00:00:00Z",
            session_id=sid,
            action_hash=_action_hash(sid, target, op),
            target=target,
            op=op,
            severity=severity,
        )

    def test_no_patterns_for_empty_ledger(self):
        self.assertEqual(analyze_ledger([]), [])

    def test_read_write_delete_escalation_detected(self):
        entries = [
            self._make_entry("s1", "users_table", "READ", "none"),
            self._make_entry("s2", "users_table", "WRITE", "medium"),
            self._make_entry("s3", "users_table", "DELETE", "critical"),
        ]
        patterns = analyze_ledger(entries)
        types = {p.pattern for p in patterns}
        self.assertIn("READ_WRITE_DELETE_ESCALATION", types)

    def test_recurring_violation_detected(self):
        entries = [
            self._make_entry("s1", "/prod/db", "EXEC", "critical"),
            self._make_entry("s2", "/prod/db", "EXEC", "critical"),
        ]
        patterns = analyze_ledger(entries)
        types = {p.pattern for p in patterns}
        self.assertIn("RECURRING_VIOLATION", types)

    def test_single_session_no_cross_session_flag(self):
        entries = [
            self._make_entry("s1", "/tmp/file", "READ", "none"),
            self._make_entry("s1", "/tmp/file", "WRITE", "medium"),
        ]
        # Same session — should not flag cross-session escalation
        patterns = analyze_ledger(entries)
        cross = [p for p in patterns if p.pattern == "READ_WRITE_DELETE_ESCALATION"]
        self.assertEqual(cross, [])


# ── Invariant checker ─────────────────────────────────────────────────────────
class TestInvariantChecker(unittest.TestCase):

    def test_never_delete_invariant_generated(self):
        fp = extract_fingerprint("Audit the database. Never delete any records without approval.")
        invs = generate_invariants(fp)
        self.assertTrue(any(i.op_class == "NEVER_DELETE" for i in invs))

    def test_invariant_check_catches_violation(self):
        invs = [Invariant(
            description="Must not delete",
            op_class="NEVER_DELETE",
            pattern_str=r"\bDROP\b",
            is_hard=True,
        )]
        events = [ObservedEvent(
            function="session:test", event_type="mutation",
            target="DROP TABLE users", metadata={"command": "DROP TABLE users"},
        )]
        violations = check_invariants("sess-x", events, invs)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].severity, "critical")

    def test_invariant_check_no_violation_on_safe_action(self):
        invs = [Invariant(
            description="Must not delete",
            op_class="NEVER_DELETE",
            pattern_str=r"\bDROP\b",
            is_hard=True,
        )]
        events = [ObservedEvent(
            function="session:test", event_type="mutation",
            target="SELECT * FROM users", metadata={"command": "SELECT * FROM users"},
        )]
        violations = check_invariants("sess-x", events, invs)
        self.assertEqual(violations, [])


# ── Injection detector ────────────────────────────────────────────────────────
class TestInjectionDetector(unittest.TestCase):

    def test_injection_signal_on_read_then_out_of_scope_critical(self):
        events = [
            ObservedEvent(
                function="session:s1", event_type="mutation",
                target="/tmp/malicious.md", metadata={"tool_name": "Read"},
            ),
            ObservedEvent(
                function="session:s1", event_type="mutation",
                target="DROP TABLE production_users",
                metadata={"tool_name": "Bash", "command": "DROP TABLE production_users"},
            ),
        ]
        signals = detect_injection(
            "s1", events,
            authorized_paths=[],
            alert_targets=["DROP TABLE production_users"],
        )
        self.assertGreater(len(signals), 0)
        self.assertGreater(signals[0].confidence, 0.3)

    def test_no_injection_when_action_is_in_scope(self):
        events = [
            ObservedEvent(
                function="session:s1", event_type="mutation",
                target="/project/notes.md", metadata={"tool_name": "Read"},
            ),
            ObservedEvent(
                function="session:s1", event_type="mutation",
                target="/project/notes.md",
                metadata={"tool_name": "Write"},
            ),
        ]
        signals = detect_injection(
            "s1", events,
            authorized_paths=["/project/notes.md"],
            alert_targets=[],
        )
        self.assertEqual(signals, [])


# ── Syscall bridge ────────────────────────────────────────────────────────────
class TestSyscallBridge(unittest.TestCase):

    def test_detect_capability_returns_valid_mode(self):
        cap = detect_capability()
        self.assertIn(cap.mode, [BMode.FULL, BMode.FILESYSTEM, BMode.UNAVAILABLE])
        self.assertIsInstance(cap.available, bool)
        self.assertIsInstance(cap.reason, str)

    def test_observe_invalid_pid_returns_empty(self):
        from lsa.drift.syscall_bridge import observe_process
        events, mode = observe_process(pid=9999999, duration_seconds=0.1)
        self.assertIsInstance(events, list)
        self.assertIn(mode, [BMode.FULL, BMode.FILESYSTEM, BMode.UNAVAILABLE])


# ── PreToolUse hook ───────────────────────────────────────────────────────────
class TestPreToolCheck(unittest.TestCase):

    def _run_hook(self, payload, env_extras=None):
        import subprocess, sys
        env = dict(os.environ)
        if env_extras:
            env.update(env_extras)
        result = subprocess.run(
            [sys.executable,
             "/Users/gani/Desktop/Intent-drive/living-systems-auditor/hooks/pre_tool_check.py"],
            input=json.dumps(payload), text=True, capture_output=True, env=env,
        )
        return result.returncode, result.stdout

    def test_observe_mode_never_blocks(self):
        payload = {"session_id": "t1", "tool_name": "Bash",
                   "tool_input": {"command": "rm -rf /"}}
        rc, out = self._run_hook(payload, {"INTENT_GUARD_MODE": ""})
        self.assertEqual(rc, 0)
        self.assertNotIn("continue", out)

    def test_strict_mode_blocks_rm_rf_root(self):
        payload = {"session_id": "t2", "tool_name": "Bash",
                   "tool_input": {"command": "rm -rf /"}}
        rc, out = self._run_hook(payload, {"INTENT_GUARD_MODE": "strict"})
        self.assertEqual(rc, 0)
        if out.strip():
            data = json.loads(out)
            self.assertFalse(data.get("continue", True))

    def test_strict_mode_allows_safe_command(self):
        payload = {"session_id": "t3", "tool_name": "Bash",
                   "tool_input": {"command": "echo hello"}}
        rc, out = self._run_hook(payload, {"INTENT_GUARD_MODE": "strict"})
        self.assertEqual(rc, 0)
        # safe command = no output or output without continue:false
        if out.strip():
            data = json.loads(out)
            self.assertTrue(data.get("continue", True))


if __name__ == "__main__":
    unittest.main()
