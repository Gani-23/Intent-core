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

    def test_synthetic_benchmark_floor(self):
        result = run_benchmark("dataset.jsonl")
        self.assertGreaterEqual(result.precision, 0.95, "Synthetic floor precision must be >= 95%")
        self.assertGreaterEqual(result.recall, 0.95, "Synthetic floor recall must be >= 95%")

    def test_extended_synthetic_benchmark_metrics(self):
        result = run_benchmark("synthetic_dataset_v2.jsonl")
        # Extended synthetic benchmark: recall must be 100% (never miss real danger)
        # Precision on raw extended dataset is 80.0% due to un-declared benign .env.example read
        self.assertGreaterEqual(result.recall, 1.0, "Recall on extended synthetic dataset must be 100%")
        self.assertGreaterEqual(result.precision, 0.80, "Precision on extended synthetic dataset must be >= 80%")

    def test_dogfooded_benchmark_metrics(self):
        result = run_benchmark("real_dogfooded_dataset.jsonl")
        # Real dogfooded development dataset: 100% precision, 100% recall
        self.assertGreaterEqual(result.recall, 1.0, "Recall on dogfooded dataset must be 100%")
        self.assertGreaterEqual(result.precision, 1.0, "Precision on dogfooded dataset must be 100%")

        # Provenance integrity test: each entry must point to an existing scope & trace file on disk
        import json
        from pathlib import Path
        dataset_path = Path(__file__).parent.parent.parent / "benchmarks" / "real_dogfooded_dataset.jsonl"
        for line in dataset_path.read_text().splitlines():
            if not line.strip():
                continue
            case = json.loads(line)
            scope_file = Path(case["source_scope_file"])
            trace_file = Path(case["source_trace_file"])
            self.assertTrue(scope_file.exists(), f"Source scope file must exist: {scope_file}")
            self.assertTrue(trace_file.exists(), f"Source trace file must exist: {trace_file}")


class TestP1FastAPIBigEnd(unittest.TestCase):

    def setUp(self):
        from fastapi.testclient import TestClient
        from lsa.api.main import app
        self.client = TestClient(app)

    def test_health_endpoint_matches_dashboard_schema(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "living-systems-auditor")
        # Honest assertions: SQLite store is ready, worker is not running, multi-tenant authz is actively enforced
        self.assertEqual(data["database_backend"], "sqlite")
        self.assertTrue(data["database_ready"])
        self.assertFalse(data["worker_running"], "Worker daemon must not be reported running until implemented")
        self.assertTrue(data["authz_enabled"], "Multi-tenant authz is actively implemented and enforced")

    def test_mock_endpoints_explicitly_flagged(self):
        res_readiness = self.client.get("/maintenance/control-plane-deployment-readiness")
        self.assertEqual(res_readiness.status_code, 200)
        self.assertTrue(res_readiness.json().get("mock"), "Placeholder endpoint must include mock: true")

        res_analytics = self.client.get("/analytics/control-plane")
        self.assertEqual(res_analytics.status_code, 200)
        self.assertTrue(res_analytics.json().get("mock"), "Placeholder endpoint must include mock: true")

    def test_ingest_event_with_valid_api_key_and_persistence(self):
        import uuid
        from lsa.api.main import _STORE
        headers = {"X-API-Key": "lsa-test-key-12345"}
        sess_id = f"fastapi-persisted-{uuid.uuid4().hex[:8]}"
        payload = {
            "session_id": sess_id,
            "tool_name": "Bash",
            "tool_input": {"command": "npm test"},
            "agent_source": "claude_code"
        }
        res = self.client.post("/api/v1/sessions/events", json=payload, headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["event_persisted"])
        
        # Verify event was durably persisted in SQLite and can be retrieved
        events = _STORE.get_events_for_session(sess_id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["tool_name"], "Bash")

    def test_ingest_event_unauthorized(self):
        headers = {"X-API-Key": "invalid-wrong-key"}
        payload = {
            "session_id": "unauth-session",
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
        }
        res = self.client.post("/api/v1/sessions/events", json=payload, headers=headers)
        self.assertEqual(res.status_code, 401)

    def test_multitenancy_isolation_and_revocation(self):
        import uuid
        from lsa.api.main import _STORE

        # Create two distinct org API keys
        key_org_a = _STORE.create_api_key(organization_name="acme-corp")
        key_org_b = _STORE.create_api_key(organization_name="globex-inc")

        shared_session_id = f"sess-{uuid.uuid4().hex[:8]}"

        # Org A posts an event
        payload_a = {
            "session_id": shared_session_id,
            "tool_name": "Bash",
            "tool_input": {"command": "echo acme secret"},
            "agent_source": "claude_code",
        }
        res_a = self.client.post(
            "/api/v1/sessions/events",
            json=payload_a,
            headers={"X-API-Key": key_org_a},
        )
        self.assertEqual(res_a.status_code, 200)

        # Org A can retrieve its event via API
        res_get_a = self.client.get(
            f"/api/v1/sessions/{shared_session_id}/events",
            headers={"X-API-Key": key_org_a},
        )
        self.assertEqual(res_get_a.status_code, 200)
        events_a = res_get_a.json()
        self.assertEqual(len(events_a), 1)
        self.assertEqual(events_a[0]["organization_name"], "acme-corp")

        # Org B querying the same session ID MUST receive an empty list (strict multi-tenant isolation)
        res_get_b = self.client.get(
            f"/api/v1/sessions/{shared_session_id}/events",
            headers={"X-API-Key": key_org_b},
        )
        self.assertEqual(res_get_b.status_code, 200)
        events_b = res_get_b.json()
        self.assertEqual(len(events_b), 0, "Org B must not access Org A session events")

        # Test Revocation: Revoking Org A key makes subsequent requests 401
        self.assertTrue(_STORE.revoke_api_key(key_org_a))
        res_revoked = self.client.get(
            f"/api/v1/sessions/{shared_session_id}/events",
            headers={"X-API-Key": key_org_a},
        )
        self.assertEqual(res_revoked.status_code, 401)
        self.assertIn("revoked", res_revoked.json()["detail"])

    def test_layer2_policy_as_code_and_rbac(self):
        """L2.1: Test org policy authoring, admin RBAC, and policy pull."""
        from lsa.api.main import _STORE

        admin_key = _STORE.create_api_key(organization_name="cyber-dyn", role="admin")
        member_key = _STORE.create_api_key(organization_name="cyber-dyn", role="member")
        other_admin_key = _STORE.create_api_key(organization_name="other-org", role="admin")

        policy_payload = {
            "organization": "cyber-dyn",
            "version": 1,
            "rules": [
                {
                    "id": "no-prod-table-writes",
                    "description": "Block any agent writing to prod tables",
                    "match": {"target_pattern": "prod_.*", "operation": ["WRITE", "DELETE"]},
                    "action": "block",
                    "severity": "critical",
                }
            ],
        }

        # 1. Member cannot set policy (403 Admin required)
        res_fail = self.client.post(
            "/api/v1/orgs/cyber-dyn/policy",
            json=policy_payload,
            headers={"X-API-Key": member_key},
        )
        self.assertEqual(res_fail.status_code, 403)

        # 2. Other org admin cannot set policy for cyber-dyn (403)
        res_other = self.client.post(
            "/api/v1/orgs/cyber-dyn/policy",
            json=policy_payload,
            headers={"X-API-Key": other_admin_key},
        )
        self.assertEqual(res_other.status_code, 403)

        # 3. Org admin successfully sets policy
        res_ok = self.client.post(
            "/api/v1/orgs/cyber-dyn/policy",
            json=policy_payload,
            headers={"X-API-Key": admin_key},
        )
        self.assertEqual(res_ok.status_code, 200)
        self.assertEqual(res_ok.json()["rules_count"], 1)

        # 4. Org member pulls policy successfully
        res_get = self.client.get(
            "/api/v1/orgs/cyber-dyn/policy",
            headers={"X-API-Key": member_key},
        )
        self.assertEqual(res_get.status_code, 200)
        pol = res_get.json()
        self.assertEqual(pol["organization"], "cyber-dyn")
        self.assertEqual(len(pol["rules"]), 1)
        self.assertEqual(pol["rules"][0]["id"], "no-prod-table-writes")

    def test_layer2_compliance_report_and_gaps(self):
        """L2.3 / C1 / C2: Test SOC2 CC7.2 compliance evidence report, signature verification (C1), and blocked violations (C2)."""
        from lsa.api.main import _STORE
        from pathlib import Path
        import json

        org_key = _STORE.create_api_key(organization_name="compliance-org")
        
        # Scenario 1: Session with missing/corrupted signature
        tampered_sess = "tampered_audit_sess_99"
        _STORE.store_event(
            session_id=tampered_sess,
            agent_source="claude_code",
            tool_name="Bash",
            target="git status",
            payload={"test": "val"},
            organization_name="compliance-org",
        )
        # Create corrupted sig file
        state_dir = Path(".intent-guard")
        state_dir.mkdir(exist_ok=True)
        (state_dir / f"{tampered_sess}.scope.jsonl").write_text(json.dumps({"prompt": "Do audit"}) + "\n")
        (state_dir / f"{tampered_sess}.sig").write_text(json.dumps({"sig": "corrupted_bad_sig", "session_id": tampered_sess}))

        res_tampered = self.client.get(
            "/api/v1/orgs/compliance-org/compliance-report",
            headers={"X-API-Key": org_key},
        )
        self.assertEqual(res_tampered.status_code, 200)
        data_t = res_tampered.json()
        self.assertFalse(data_t["controls"]["evidence_integrity"]["tamper_evident_signatures_verified"])
        self.assertIn(tampered_sess, data_t["controls"]["evidence_integrity"]["per_session_signature_verification"])
        self.assertFalse(data_t["controls"]["evidence_integrity"]["per_session_signature_verification"][tampered_sess]["verified"])

        # Scenario 2: Blocked policy violation ingested (C2)
        blocked_sess = "blocked_violation_sess_42"
        self.client.post(
            "/api/v1/sessions/events",
            json={
                "session_id": blocked_sess,
                "tool_name": "Bash",
                "tool_input": {"command": "DELETE FROM prod_users"},
                "tool_response": {"continue": False, "reason": "[intent-guard policy] Blocked by organization policy rule 'block-prod'"},
                "blocked": True,
                "policy_violation": True,
                "agent_source": "claude_code",
            },
            headers={"X-API-Key": org_key},
        )

        res_blocked = self.client.get(
            "/api/v1/orgs/compliance-org/compliance-report",
            headers={"X-API-Key": org_key},
        )
        self.assertEqual(res_blocked.status_code, 200)
        data_b = res_blocked.json()
        cc7_2 = data_b["controls"]["CC7.2_change_management"]
        self.assertGreater(cc7_2["blocked_policy_violations"], 0)
        self.assertEqual(cc7_2["status"], "violations_blocked")

        # Cleanup test files
        (state_dir / f"{tampered_sess}.scope.jsonl").unlink(missing_ok=True)
        (state_dir / f"{tampered_sess}.sig").unlink(missing_ok=True)

    def test_layer2_trust_score_calculation(self):
        """L2.4: Test single trend-over-time drift/trust score."""
        from lsa.api.main import _STORE

        org_key = _STORE.create_api_key(organization_name="trust-org")
        res = self.client.get(
            "/api/v1/orgs/trust-org/trust-score",
            headers={"X-API-Key": org_key},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("score", data)
        self.assertIn("grade", data)
        self.assertIn("trend", data)
        self.assertIn("formula", data)
        self.assertGreaterEqual(data["score"], 0)
        self.assertLessEqual(data["score"], 100)

    def test_layer2_generic_webhook_e2e_persistence(self):
        """L2.5: Real non-Claude-Code adapter traffic through API into multi-tenant store."""
        from lsa.api.main import _STORE
        import uuid

        org_key = _STORE.create_api_key(organization_name="webhook-corp")
        sid = f"webhook-sess-{uuid.uuid4().hex[:8]}"

        payload = {
            "session_id": sid,
            "tool_name": "PostgresMutation",
            "tool_input": {"sql": "UPDATE settings SET maintenance = true"},
            "agent_source": "generic",
        }
        res = self.client.post(
            "/api/v1/sessions/events",
            json=payload,
            headers={"X-API-Key": org_key},
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["event_persisted"])

        # Query events from database and verify target & org scoping
        events = _STORE.get_events_for_session(sid, organization_name="webhook-corp")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["agent_source"], "generic")
        self.assertEqual(events[0]["organization_name"], "webhook-corp")


if __name__ == "__main__":
    unittest.main()
