from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch, MagicMock

from action.pr_commenter import (
    format_pr_comment,
    post_or_update_pr_comment,
    resolve_pr_number,
    sanitize_markdown_details,
    collect_local_reports,
    dynamic_pr_audit,
    REPORT_MARKER,
)
from lsa.api.rate_limiter import SlidingWindowRateLimiter, TokenBucketRateLimiter
from lsa.reports.state_of_drift import generate_state_of_drift_report, MIN_SESSIONS_THRESHOLD
from lsa.storage.sqlite_store import SQLiteEventStore
import lsa.drift.syscall_bridge as sb


class Layer3AndHardeningTests(unittest.TestCase):

    def setUp(self) -> None:
        from lsa.api.rate_limiter import get_rate_limiter
        get_rate_limiter().clear()

    def tearDown(self) -> None:
        from lsa.api.rate_limiter import get_rate_limiter
        get_rate_limiter().clear()

    def test_pr_comment_formatting(self) -> None:
        clean_comment = format_pr_comment([])
        self.assertIn(REPORT_MARKER, clean_comment)
        self.assertIn("No drift detected this session", clean_comment)

        drift_comment = format_pr_comment([{"session_id": "sess-2", "findings_count": 2, "content": "Findings details"}])
        self.assertIn(REPORT_MARKER, drift_comment)
        self.assertIn("2 finding(s) detected", drift_comment)

    def test_pr_comment_idempotent_post_and_patch(self) -> None:
        # 1. New comment case
        with patch("urllib.request.urlopen") as mock_url:
            mock_url.return_value.__enter__.return_value.read.side_effect = [
                b"[]",
                b'{"id": 42, "html_url": "https://github.com/org/repo/pull/1#issuecomment-42"}',
            ]
            action, cid = post_or_update_pr_comment("org/repo", 1, "fake-token", "Report text")
            self.assertEqual(action, "created")
            self.assertEqual(cid, 42)

        # 2. Existing comment case
        with patch("urllib.request.urlopen") as mock_url:
            mock_url.return_value.__enter__.return_value.read.side_effect = [
                b'[{"id": 42, "body": "<!-- intent-guard-report-marker -->\\nPrior"}]',
                b'{"id": 42, "html_url": "https://github.com/org/repo/pull/1#issuecomment-42"}',
            ]
            action, cid = post_or_update_pr_comment("org/repo", 1, "fake-token", "Updated text")
            self.assertEqual(action, "updated")
            self.assertEqual(cid, 42)

    def test_post_or_update_pr_comment_never_logs_token_prefix(self) -> None:
        import io
        import sys

        # Test both default mode and INTENT_GUARD_DEBUG=1 mode
        for debug_val in ("", "1"):
            stderr_capture = io.StringIO()
            with patch("urllib.request.urlopen") as mock_url, \
                 patch.dict(os.environ, {"INTENT_GUARD_DEBUG": debug_val}, clear=False), \
                 patch("sys.stderr", stderr_capture):
                mock_url.return_value.__enter__.return_value.read.side_effect = [
                    b"[]",
                    b'{"id": 42, "html_url": "https://github.com/org/repo/pull/1#issuecomment-42"}',
                ]
                post_or_update_pr_comment("org/repo", 1, "ghp_SECRET_TOKEN_VALUE", "Body text")
                logged = stderr_capture.getvalue()
                self.assertNotIn("prefix=", logged)
                self.assertNotIn("ghp_", logged)
                self.assertNotIn("SECRET", logged)

    def test_dynamic_pr_audit_when_engine_fails_to_load_reports_audit_not_performed(self) -> None:
        import sys
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            rep_dir = Path(td)
            files = [{"filename": "secret_production.env", "status": "modified", "patch": "+SECRET=123"}]
            with patch.dict(sys.modules, {"lsa.drift.diff_audit": None}):
                report_path = dynamic_pr_audit("org/repo", 99, "benign title", "benign body", files, rep_dir)
                self.assertIsNotNone(report_path)
                content = report_path.read_text(encoding="utf-8")

                # Must explicitly warn that audit was not performed
                self.assertIn("⚠️ **Audit Not Performed**", content)
                self.assertIn("the drift detection engine could not be loaded in this environment", content)
                # Must NEVER claim Clean Pass when check failed to run
                self.assertNotIn("Clean Pass", content)

                # PR comment formatting must reflect audit not performed
                collected = collect_local_reports(rep_dir)
                comment = format_pr_comment(collected)
                self.assertIn("⚠️ **audit not performed**", comment)
                self.assertNotIn("clean pass", comment)

    def test_dynamic_pr_audit_clean_pass_and_drift_detection(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            rep_dir = Path(td)

            # 1. Clean pass case: declared file matches mutation
            files_clean = [{"filename": "src/app.py", "status": "modified", "patch": "+print('hello')"}]
            p_clean = dynamic_pr_audit("org/repo", 101, "Update src/app.py", "Modify app logic in src/app.py", files_clean, rep_dir)
            content_clean = p_clean.read_text(encoding="utf-8")
            self.assertIn("✅ **Clean Pass**", content_clean)
            self.assertNotIn("Audit Not Performed", content_clean)

            # 2. Drift case: secret file touched without declaration
            files_drift = [{"filename": ".env.local", "status": "added", "patch": "+KEY=val"}]
            p_drift = dynamic_pr_audit("org/repo", 102, "Docs update", "Just updating docs", files_drift, rep_dir)
            content_drift = p_drift.read_text(encoding="utf-8")
            self.assertIn(".env.local", content_drift)
            self.assertNotIn("Clean Pass", content_drift)

    def test_dynamic_pr_audit_doc_comment_false_positive_prevention(self) -> None:
        """Regression test 1: documentation comment in code describing dangerous patterns must NOT be flagged."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            rep_dir = Path(td)
            doc_diff = [
                {
                    "filename": "lsa/drift/mutation_rules.py",
                    "status": "modified",
                    "patch": (
                        "@@ -95,3 +95,5 @@\n"
                        "+    # Example: rm -rf / or filesystem-wide delete matches this pattern\n"
                        "+    # Maintainers document security rules with spaces like rm -rf $GITHUB_WORKSPACE\n"
                    ),
                }
            ]
            report_path = dynamic_pr_audit(
                "org/repo",
                103,
                "docs: clarify mutation rules regex",
                "Documenting regex patterns in lsa/drift/mutation_rules.py",
                doc_diff,
                rep_dir,
            )
            content = report_path.read_text(encoding="utf-8")
            self.assertIn("✅ **Clean Pass**", content)
            self.assertNotIn("destructive pattern", content)
            self.assertNotIn("[HIGH]", content)
            self.assertNotIn("[CRITICAL]", content)

    def test_dynamic_pr_audit_executable_surface_destructive_command_detected(self) -> None:
        """Regression test 2: real destructive command added to executable surface (e.g. CI workflow) MUST be flagged."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            rep_dir = Path(td)
            malicious_workflow = [
                {
                    "filename": ".github/workflows/deploy.yml",
                    "status": "modified",
                    "patch": (
                        "@@ -20,3 +20,5 @@\n"
                        "+    - name: Cleanup workspace\n"
                        "+      run: rm -rf $GITHUB_WORKSPACE\n"
                    ),
                }
            ]
            report_path = dynamic_pr_audit(
                "org/repo",
                104,
                "ci: add deploy step",
                "Updating deployment workflow",
                malicious_workflow,
                rep_dir,
            )
            content = report_path.read_text(encoding="utf-8")
            self.assertIn("[CRITICAL]", content)
            self.assertIn("destructive command", content)
            self.assertIn("workspace-wide delete", content)
            self.assertNotIn("Clean Pass", content)

    def test_no_tracked_files_under_intent_guard_directory(self) -> None:
        """Enforce that no files under .intent-guard/ are tracked in git index."""
        import subprocess

        res = subprocess.run(["git", "ls-files", ".intent-guard/"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        tracked = res.stdout.strip()
        self.assertEqual(tracked, "", f"Found tracked files under .intent-guard/: {tracked}")

    def test_resolve_pr_number_from_env_and_event_payload(self) -> None:
        import tempfile

        # 1. From PR_NUMBER env var
        with patch.dict(os.environ, {"PR_NUMBER": "123"}, clear=False):
            self.assertEqual(resolve_pr_number(), 123)

        # 2. From GITHUB_EVENT_PATH pull_request payload
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as tf:
            tf.write('{"pull_request": {"number": 456}}')
            tf.flush()
            with patch.dict(os.environ, {"PR_NUMBER": "", "GITHUB_EVENT_PATH": tf.name}, clear=False):
                self.assertEqual(resolve_pr_number(), 456)

        # 3. From GITHUB_EVENT_PATH issue_comment on a PR
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as tf:
            tf.write('{"issue": {"number": 789, "pull_request": {"html_url": "https://..."}}}')
            tf.flush()
            with patch.dict(os.environ, {"PR_NUMBER": "", "GITHUB_EVENT_PATH": tf.name}, clear=False):
                self.assertEqual(resolve_pr_number(), 789)

        # 4. Non-PR event (e.g., push event)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as tf:
            tf.write('{"ref": "refs/heads/main", "commits": []}')
            tf.flush()
            with patch.dict(os.environ, {"PR_NUMBER": "", "GITHUB_EVENT_PATH": tf.name}, clear=False):
                self.assertIsNone(resolve_pr_number())

    def test_sanitize_markdown_details(self) -> None:
        # 1. Escapes simple <details> tags
        payload = "<details>malicious</details>"
        sanitized = sanitize_markdown_details(payload)
        self.assertNotIn("<details>", sanitized)
        self.assertIn("&lt;details&gt;", sanitized)

        # 2. Escapes tags with attributes: <details open>...</details open>
        attr_payload = "<details open>forged section</details open>"
        attr_sanitized = sanitize_markdown_details(attr_payload)
        self.assertEqual(attr_sanitized, "&lt;details open&gt;forged section&lt;/details open&gt;")

        # 3. Case-insensitive tags: </DETAILS>
        case_payload = "</DETAILS>"
        case_sanitized = sanitize_markdown_details(case_payload)
        self.assertEqual(case_sanitized, "&lt;/DETAILS&gt;")

        # 4. Summary tags: <summary>fake summary</summary>
        summary_payload = "<summary>fake summary</summary>"
        summary_sanitized = sanitize_markdown_details(summary_payload)
        self.assertEqual(summary_sanitized, "&lt;summary&gt;fake summary&lt;/summary&gt;")

        # 5. Irregular internal whitespace/newlines: < details \n open >
        irregular_payload = "< details \n open >"
        irregular_sanitized = sanitize_markdown_details(irregular_payload)
        self.assertEqual(irregular_sanitized, "&lt; details \n open &gt;")

        # 6. Caps excessive length
        oversized = "a" * 20000
        truncated = sanitize_markdown_details(oversized, max_length=1000)
        self.assertLessEqual(len(truncated), 1100)
        self.assertIn("Report truncated", truncated)

    def test_health_and_auth_unconditional_consistency(self) -> None:
        from fastapi.testclient import TestClient
        from lsa.api.main import app

        client = TestClient(app)
        # Even if LSA_DISABLE_AUTH=1 is set, authz_enabled remains True (Option A)
        # and unauthenticated protected requests still receive 401.
        with patch.dict(os.environ, {"LSA_DISABLE_AUTH": "1"}, clear=False):
            health_res = client.get("/health")
            self.assertEqual(health_res.status_code, 200)
            data = health_res.json()
            self.assertTrue(data["authz_enabled"])
            self.assertTrue(data["auth_required"])

            # Request to protected endpoint must return 401
            prot_res = client.post(
                "/api/v1/sessions/events",
                json={
                    "session_id": "test-session",
                    "tool_name": "Bash",
                    "tool_input": {"command": "ls"},
                },
            )
            self.assertEqual(prot_res.status_code, 401)
            self.assertEqual(prot_res.json(), {"detail": "Missing X-API-Key header"})

    def test_rate_limiter_sliding_window(self) -> None:
        self.assertIs(TokenBucketRateLimiter, SlidingWindowRateLimiter)
        limiter = SlidingWindowRateLimiter(requests_per_minute=3)
        # 3 calls should pass
        for _ in range(3):
            allowed, _ = limiter.check_rate_limit("user-key")
            self.assertTrue(allowed)

        # 4th call immediately should be throttled
        allowed, retry_after = limiter.check_rate_limit("user-key")
        self.assertFalse(allowed)
        self.assertGreater(retry_after, 0)

        # Peer key should be unaffected
        peer_allowed, _ = limiter.check_rate_limit("peer-key")
        self.assertTrue(peer_allowed)

    def test_windows_syscall_transparency(self) -> None:
        with patch.object(sb, "_IS_MACOS", False), patch.object(sb, "_IS_LINUX", False), patch.object(sb, "_IS_WINDOWS", True):
            cap = sb.detect_capability()
            self.assertEqual(cap.mode, sb.ObservationMode.UNAVAILABLE)
            events, mode = sb.observe_process(1234)
            self.assertEqual(mode, sb.ObservationMode.UNAVAILABLE)
            self.assertEqual(events, [])

    def test_state_of_drift_k_anonymity_guard(self) -> None:
        store = SQLiteEventStore()
        # Test aggregation logic
        report = generate_state_of_drift_report(store)
        self.assertIn("anonymization_safety", report)
        anon = report["anonymization_safety"]
        self.assertIn("is_sufficient_for_public_release", anon)
        self.assertIn("observed_sessions", anon)
        self.assertIn("required_sessions_threshold", anon)
        if anon["observed_sessions"] < MIN_SESSIONS_THRESHOLD:
            self.assertFalse(anon["is_sufficient_for_public_release"])

    def test_b1_capture_event_classifies_read_and_triggers_injection(self) -> None:
        from hooks.capture_event import classify
        from lsa.drift.models import ObservedEvent
        from lsa.drift.injection_detector import detect_injection

        # 1. classify() must handle Read
        classified = classify("Read", {"file_path": "/workspace/instructions.md"})
        self.assertEqual(classified, ("/workspace/instructions.md", "", "Read"))

        # 2. Causal injection detection on classified events
        events = [
            ObservedEvent(
                function="session:test",
                event_type="read",
                target="/workspace/instructions.md",
                metadata={"tool_name": "Read"},
            ),
            ObservedEvent(
                function="session:test",
                event_type="mutation",
                target="DROP TABLE users",
                metadata={"tool_name": "Bash", "command": "DROP TABLE users"},
            ),
        ]
        signals = detect_injection("test", events, authorized_paths=[], alert_targets=["DROP TABLE users"])
        self.assertGreater(len(signals), 0)
        self.assertEqual(signals[0].read_target, "/workspace/instructions.md")
        self.assertEqual(signals[0].triggered_action, "DROP TABLE users")

    def test_b2_scope_authorization_thread_paths_and_unmentioned_detection(self) -> None:
        from lsa.drift.intent_fingerprint import extract_fingerprint
        from lsa.drift.mutation_rules import MutationComparator, SessionScope
        from lsa.drift.models import ObservedEvent
        from fastapi.testclient import TestClient
        from lsa.api.main import app

        # 1. Legitimate .env touch in task mentioning .env
        task_env = "Please rotate secrets in .env"
        fp_env = extract_fingerprint(task_env)
        self.assertIn(".env", fp_env.authorized_paths)
        scope_env = SessionScope(task_text=task_env, known_paths=fp_env.authorized_paths)
        ev_env = ObservedEvent(function="s", event_type="mutation", target=".env", metadata={"command": "echo KEY=1 >> .env"})
        alerts_env = MutationComparator().compare(scope_env, [ev_env])
        self.assertEqual(len(alerts_env), 0)

        # 2. Unmentioned target when task defines other paths
        task_auth = "Fix login logic in auth.py"
        fp_auth = extract_fingerprint(task_auth)
        scope_auth = SessionScope(task_text=task_auth, known_paths=fp_auth.authorized_paths)
        ev_other = ObservedEvent(function="s", event_type="mutation", target="payments.py", metadata={"command": "touch payments.py"})
        alerts_other = MutationComparator().compare(scope_auth, [ev_other])
        self.assertGreater(len(alerts_other), 0)
        self.assertIn("Target was not mentioned anywhere", alerts_other[0].reason)

        # 3. Via evaluate-incident endpoint
        client = TestClient(app)
        res_env = client.post(
            "/api/v1/audit/evaluate-incident",
            json={"task_text": "Update credentials in .env", "command": "echo A=1 >> .env", "tool_name": "Bash"},
        )
        self.assertFalse(res_env.json()["caught"])

        res_other = client.post(
            "/api/v1/audit/evaluate-incident",
            json={"task_text": "Fix login logic in auth.py", "command": "touch payments.py", "tool_name": "Bash"},
        )
        self.assertTrue(res_other.json()["caught"])

    def test_b3_remediation_provider_preference_resolution(self) -> None:
        from lsa.remediation.llm_client import build_remediation_client, FailsafeRemediationClient, RemediationRuntimeStatus
        from hooks.session_report import _Settings

        # Test _Settings propagates INTENT_GUARD_PROVIDER to preferred_provider
        with patch.dict(os.environ, {"INTENT_GUARD_PROVIDER": "anthropic"}, clear=False):
            settings = _Settings()
            self.assertEqual(settings.remediation_provider, "anthropic")
            self.assertEqual(settings.preferred_provider, "anthropic")

        # Test build_remediation_client uses remediation_provider if preferred_provider is absent
        class LegacySettings:
            def __init__(self) -> None:
                self.remediation_provider = "anthropic"
                self.remediation_timeout_seconds = 20.0

        with patch("lsa.remediation.llm_client.inspect_remediation_runtime") as mock_inspect:
            mock_inspect.return_value = RemediationRuntimeStatus(
                provider="failsafe", model=None, base_url=None, enabled=True,
                available=True, fallback_active=True, configured=True, blockers=[]
            )
            client = build_remediation_client(LegacySettings())
            self.assertIsInstance(client, FailsafeRemediationClient)
            self.assertEqual(client.preferred_provider, "anthropic")

    def test_b4_resolve_agent_pid_never_returns_self_pid(self) -> None:
        from hooks.session_report import resolve_agent_pid

        # 1. From payload
        self.assertEqual(resolve_agent_pid({"agent_pid": 8888}), 8888)

        # 2. From env
        with patch.dict(os.environ, {"CLAUDE_CODE_PID": "9999"}, clear=False):
            self.assertEqual(resolve_agent_pid({}), 9999)

        # 3. From process tree (never self PID)
        with patch.dict(os.environ, {}, clear=False):
            resolved = resolve_agent_pid({})
            self.assertNotEqual(resolved, os.getpid())
            if resolved is not None:
                self.assertGreater(resolved, 1)

    def test_c1_default_api_key_gated_to_dev_and_test(self) -> None:
        import tempfile
        import importlib
        from fastapi.testclient import TestClient

        # In production without LSA_API_KEY, lsa-test-key-12345 must be rejected
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "test_prod.db")
            with patch.dict(os.environ, {"LSA_STORE_PATH": db_path, "LSA_ENV": "production"}, clear=False):
                if "LSA_API_KEY" in os.environ:
                    del os.environ["LSA_API_KEY"]
                if "PYTEST_CURRENT_TEST" in os.environ:
                    del os.environ["PYTEST_CURRENT_TEST"]
                import lsa.api.main as m
                importlib.reload(m)
                client = TestClient(m.app)
                res = client.post(
                    "/api/v1/sessions/events",
                    headers={"X-API-Key": "lsa-test-key-12345"},
                    json={"session_id": "s", "tool_name": "Bash", "tool_input": {"command": "ls"}},
                )
                self.assertEqual(res.status_code, 401)
                self.assertEqual(res.json(), {"detail": "Invalid API key"})


if __name__ == "__main__":
    unittest.main()
