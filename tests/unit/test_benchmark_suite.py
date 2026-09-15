from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from lsa.cli import main
from lsa.drift.benchmark import run_benchmark, BENCHMARK_SCENARIOS


class BenchmarkSuiteTests(unittest.TestCase):

    def test_empirical_benchmark_100_percent_accuracy(self) -> None:
        report = run_benchmark()
        self.assertEqual(report.total_scenarios, 20)
        self.assertEqual(report.passed_scenarios, 20)
        self.assertEqual(report.failed_scenarios, 0)
        self.assertEqual(report.accuracy_percentage, 100.0)
        self.assertEqual(report.true_positive_rate, 100.0)
        self.assertEqual(report.true_negative_rate, 100.0)
        self.assertEqual(report.precision_percentage, 100.0)
        self.assertLess(report.avg_latency_ms, 5.0)  # Sub-millisecond target

    def test_cli_check_drift_blocked(self) -> None:
        # Destructive root deletion during CSS edit -> exit code 1
        rc = main(["check", "-t", "Fix CSS on navbar", "-c", "rm -rf /"])
        self.assertEqual(rc, 1)

    def test_cli_check_safe_permitted(self) -> None:
        # Safe git diff -> exit code 0
        rc = main(["check", "-t", "Fix CSS on navbar", "-c", "git diff src/style.css"])
        self.assertEqual(rc, 0)

    def test_cli_check_json_output(self) -> None:
        import io
        from unittest.mock import patch

        f = io.StringIO()
        with patch("sys.stdout", f):
            rc = main(["check", "-t", "Fix CSS", "-c", "rm -rf /", "--json"])
        self.assertEqual(rc, 1)
        data = json.loads(f.getvalue())
        self.assertTrue(data["caught"])
        self.assertEqual(data["verdict"], "BLOCKED_AS_DRIFT")

    def test_cli_gate_valid_bundle(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
            json.dump({
                "bundle_version": "1.0",
                "valid": True,
                "target_profile": "test-env",
                "blockers": [],
            }, tf)
            tf_path = tf.name

        try:
            rc = main(["gate", "-p", tf_path])
            self.assertEqual(rc, 0)
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def test_cli_gate_blocked_bundle(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
            json.dump({
                "bundle_version": "1.0",
                "valid": False,
                "target_profile": "test-env",
                "blockers": ["Unsigned critical migration observed"],
            }, tf)
            tf_path = tf.name

        try:
            rc = main(["gate", "-p", tf_path])
            self.assertEqual(rc, 1)
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def test_cli_gate_missing_bundle(self) -> None:
        rc = main(["gate", "-p", "/nonexistent/path/bundle.json"])
        self.assertEqual(rc, 2)

    def test_cli_benchmark_command(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out_json = Path(td) / "benchmark.json"
            out_md = Path(td) / "benchmark.md"
            rc = main(["benchmark", "-o", str(out_json), "-m", str(out_md)])
            self.assertEqual(rc, 0)
            self.assertTrue(out_json.exists())
            self.assertTrue(out_md.exists())
            data = json.loads(out_json.read_text())
            self.assertEqual(data["total_scenarios"], 20)

    def test_cli_hook_command(self) -> None:
        rc = main(["hook"])
        self.assertEqual(rc, 0)
        hook_path = Path(".intent-guard/hooks/pre-tool.sh")
        self.assertTrue(hook_path.exists())
        self.assertTrue(os.access(hook_path, os.X_OK))


if __name__ == "__main__":
    unittest.main()
