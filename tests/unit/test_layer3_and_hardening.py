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
    REPORT_MARKER,
)
from lsa.api.rate_limiter import SlidingWindowRateLimiter, TokenBucketRateLimiter
from lsa.reports.state_of_drift import generate_state_of_drift_report, MIN_SESSIONS_THRESHOLD
from lsa.storage.sqlite_store import SQLiteEventStore
import lsa.drift.syscall_bridge as sb


class Layer3AndHardeningTests(unittest.TestCase):

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


if __name__ == "__main__":
    unittest.main()
