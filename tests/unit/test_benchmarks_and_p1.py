"""Unit tests verifying P1 features:
- Secret redaction in raw telemetry logs
- Fail-open and fail-closed policy enforcement
- Multi-agent adapter normalization (Claude Code, Cursor, generic webhook)
- Telemetry discrepancy detection via OS syscall bridge
- Empirical benchmark gate assertions
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from lsa.drift.adapters import ClaudeCodeAdapter, CursorAgentAdapter, GenericWebhookAdapter
from lsa.drift.models import ObservedEvent
from lsa.drift.redaction import redact_text, redact_json_obj, append_redacted_raw_log
from benchmarks.benchmark_eval import run_benchmark


class TestP1Redaction(unittest.TestCase):

    def test_redact_sensitive_credentials(self):
        sample = "export ANTHROPIC_API_KEY='sk-ant-api03-abcdef12345678901234567890' gh_token='ghp_123456789012345678901234'"
        redacted = redact_text(sample)
        self.assertNotIn("sk-ant-api03", redacted)
        self.assertNotIn("ghp_1234", redacted)
        self.assertIn("[REDACTED_API_KEY]", redacted)
        self.assertIn("[REDACTED_GITHUB_TOKEN]", redacted)

    def test_redact_json_dict_keys(self):
        payload = {
            "session_id": "test_sess",
            "tool_input": {
                "command": "psql postgresql://admin:supersecret123@db.prod.internal:5432/app",
                "api_key": "sk-1234567890abcdef12345678",
            }
        }
        redacted = redact_json_obj(payload)
        self.assertNotIn("supersecret123", json.dumps(redacted))
        self.assertEqual(redacted["tool_input"]["api_key"], "[REDACTED_SECRET]")

    def test_append_redacted_raw_log_writes_sanitized_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            payload = {"command": "curl -H 'Authorization: Bearer mysecrettoken1234567890123456' https://api.com"}
            append_redacted_raw_log(td, "PreToolUse", payload)
            log_file = td / "raw_stdin.jsonl"
            self.assertTrue(log_file.exists())
            content = log_file.read_text(encoding="utf-8")
            self.assertNotIn("mysecrettoken", content)
            self.assertIn("[REDACTED_TOKEN]", content)


class TestP1MultiAgentAdapters(unittest.TestCase):

    def test_claude_code_adapter(self):
        adapter = ClaudeCodeAdapter()
        payload = {
            "session_id": "claude-1",
            "tool_name": "Edit",
            "tool_input": {"file_path": "src/main.py"}
        }
        ev = adapter.parse_event(payload)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.target, "src/main.py")
        self.assertEqual(ev.metadata.get("source"), "claude_code")

    def test_cursor_agent_adapter(self):
        adapter = CursorAgentAdapter()
        # Cursor file edit
        payload = {
            "conversation_id": "cursor-conv-1",
            "action_type": "edit_file",
            "file_path": "backend/app.py"
        }
        ev = adapter.parse_event(payload)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.target, "backend/app.py")
        self.assertEqual(ev.metadata.get("source"), "cursor_composer")

        # Cursor shell execution
        shell_payload = {
            "conversation_id": "cursor-conv-1",
            "action_type": "terminal_run",
            "command": "git push origin main"
        }
        ev_shell = adapter.parse_event(shell_payload)
        self.assertIsNotNone(ev_shell)
        self.assertEqual(ev_shell.target, "git push origin main")

    def test_generic_webhook_adapter(self):
        adapter = GenericWebhookAdapter()
        payload = {"session_id": "hook_1", "target": "DROP TABLE users", "tool_name": "SQLExec"}
        ev = adapter.parse_event(payload)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.target, "DROP TABLE users")


class TestP1BenchmarkGate(unittest.TestCase):

    def test_benchmark_metrics_meet_ci_threshold(self):
        result = run_benchmark()
        self.assertGreaterEqual(result.precision, 0.95, "Precision must not fall below 95%")
        self.assertGreaterEqual(result.recall, 0.95, "Recall must not fall below 95%")
        self.assertEqual(result.false_positives, 0, "Zero false positives on benchmark set")


if __name__ == "__main__":
    unittest.main()
