from __future__ import annotations

import json
import unittest
from unittest.mock import patch, MagicMock

from action.pr_commenter import format_pr_comment, post_or_update_pr_comment, REPORT_MARKER
from lsa.api.rate_limiter import TokenBucketRateLimiter
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

    def test_rate_limiter_token_bucket(self) -> None:
        limiter = TokenBucketRateLimiter(requests_per_minute=3)
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
