from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from lsa.core.models import FunctionIntent
from lsa.drift.models import DriftAlert, ObservedEvent
from lsa.drift.mutation_rules import SessionScope
from lsa.drift.semantic_review import SemanticSessionReviewer
from lsa.remediation.failsafe import (
    clean_json_response,
    call_ai_json_with_failsafe,
    get_available_ai_providers,
)
from lsa.remediation.llm_client import (
    FailsafeRemediationClient,
    RuleBasedLLMClient,
    build_remediation_client,
    inspect_remediation_runtime,
)


class AIFailsafeTests(unittest.TestCase):

    def test_clean_json_response_parses_clean_and_fenced_json(self) -> None:
        raw_clean = '{"status": "ok", "value": 42}'
        self.assertEqual(clean_json_response(raw_clean), {"status": "ok", "value": 42})

        raw_fenced = "```json\n{\"findings\": [{\"target\": \"users\", \"severity\": \"critical\"}]}\n```"
        self.assertEqual(clean_json_response(raw_fenced), {"findings": [{"target": "users", "severity": "critical"}]})

        raw_fenced_plain = "```\n{\"result\": true}\n```"
        self.assertEqual(clean_json_response(raw_fenced_plain), {"result": True})

        with self.assertRaises(ValueError):
            clean_json_response("This is not json at all")

    def test_provider_availability_returns_booleans_only(self) -> None:
        providers = get_available_ai_providers()
        self.assertIsInstance(providers, dict)
        for key, val in providers.items():
            self.assertIsInstance(val, bool, f"Provider {key} value must be a strict boolean")
        self.assertTrue(providers["deterministic"])

    @patch("lsa.remediation.failsafe.call_anthropic_json")
    @patch("lsa.remediation.failsafe.call_openai_json")
    def test_failsafe_cascades_from_anthropic_to_openai_on_failure(
        self, mock_openai: MagicMock, mock_anthropic: MagicMock
    ) -> None:
        mock_anthropic.side_effect = ConnectionError("Anthropic API unreachable")
        mock_openai.return_value = {"findings": [{"target": "db", "severity": "high", "reason": "drift"}]}

        with patch("lsa.remediation.failsafe.get_available_ai_providers") as mock_avail:
            mock_avail.return_value = {
                "anthropic": True,
                "openai": True,
                "gemini": False,
                "antigravity": False,
                "deterministic": True,
            }
            res, provider = call_ai_json_with_failsafe(system="sys", user_prompt="prompt")

        self.assertEqual(provider, "openai")
        self.assertEqual(res["findings"][0]["target"], "db")
        mock_anthropic.assert_called_once()
        mock_openai.assert_called_once()

    @patch("lsa.remediation.failsafe.call_anthropic_json")
    @patch("lsa.remediation.failsafe.call_openai_json")
    @patch("lsa.remediation.failsafe.call_gemini_json")
    def test_failsafe_cascades_to_gemini_when_prior_fail(
        self, mock_gemini: MagicMock, mock_openai: MagicMock, mock_anthropic: MagicMock
    ) -> None:
        mock_anthropic.side_effect = TimeoutError("Anthropic timeout")
        mock_openai.side_effect = RuntimeError("OpenAI rate limit")
        mock_gemini.return_value = {"summary": "Gemini caught drift", "risk": "HIGH"}

        with patch("lsa.remediation.failsafe.get_available_ai_providers") as mock_avail:
            mock_avail.return_value = {
                "anthropic": True,
                "openai": True,
                "gemini": True,
                "antigravity": False,
                "deterministic": True,
            }
            res, provider = call_ai_json_with_failsafe(system="sys", user_prompt="prompt")

        self.assertEqual(provider, "gemini")
        self.assertEqual(res["summary"], "Gemini caught drift")

    @patch("lsa.drift.semantic_review.call_ai_json_with_failsafe")
    def test_semantic_reviewer_falls_back_to_deterministic_when_all_ai_fail(
        self, mock_failsafe: MagicMock
    ) -> None:
        mock_failsafe.side_effect = RuntimeError("All AI providers down")

        reviewer = SemanticSessionReviewer()
        scope = SessionScope(task_text="Read-only audit of billing records. Do not modify anything.")
        events = [
            ObservedEvent(
                function="session:test",
                event_type="mutation",
                target="UPDATE billing SET paid=true WHERE id=10",
                metadata={"command": "psql -c 'UPDATE billing SET paid=true WHERE id=10'"},
            )
        ]

        alerts = reviewer.review(scope, events)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].severity, "critical")
        self.assertIn("deterministic-failsafe", alerts[0].reason)
        self.assertIn("UPDATE", alerts[0].reason)

    def test_failsafe_remediation_client_generates_report(self) -> None:
        client = FailsafeRemediationClient()
        func = FunctionIntent(name="test_fn", module="core", qualname="core:test_fn", lineno=1, end_lineno=5)
        alert = DriftAlert(
            function="core:test_fn",
            observed_target="api.unauthorized.com:443",
            expected_targets=["api.stripe.com"],
            severity="high",
            reason="Unsanctioned network destination",
        )
        report = client.analyze(func, alert, prompt="Explain drift")
        self.assertIsNotNone(report.title)
        self.assertIn(report.risk, ("HIGH", "CRITICAL", "MEDIUM", "LOW"))
        markdown = report.to_markdown()
        self.assertIn("# Drift report for core:test_fn", markdown)

    def test_inspect_remediation_runtime_detects_failsafe(self) -> None:
        class Settings:
            remediation_provider = "failsafe"
            enable_remediation_model = True
            remediation_fallback_enabled = True

        status = inspect_remediation_runtime(Settings())
        self.assertEqual(status.provider, "failsafe")
        self.assertTrue(status.available)
        self.assertTrue(status.configured)


if __name__ == "__main__":
    unittest.main()
