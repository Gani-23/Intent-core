from __future__ import annotations

import unittest

from lsa.drift.models import ObservedEvent
from lsa.drift.mutation_rules import MutationComparator, SessionScope


class MutationRulesTests(unittest.TestCase):

    def test_destructive_success_vs_failure_severity(self) -> None:
        scope = SessionScope(task_text="Perform audit. Do not delete anything.")

        # Case 1: Destructive command that succeeded
        successful_event = ObservedEvent(
            function="session:test",
            event_type="mutation",
            target="rm -rf /tmp/data",
            metadata={"command": "rm -rf /tmp/data", "success": True, "exit_code": 0},
        )
        alerts_success = MutationComparator().compare(scope, [successful_event])
        self.assertEqual(len(alerts_success), 1)
        self.assertEqual(alerts_success[0].severity, "critical")
        self.assertNotIn("execution failed", alerts_success[0].reason)

        # Case 2: Destructive command that failed / was denied (exit_code != 0)
        failed_event = ObservedEvent(
            function="session:test",
            event_type="mutation",
            target="rm -rf /tmp/data",
            metadata={"command": "rm -rf /tmp/data", "success": False, "exit_code": 1},
        )
        alerts_failed = MutationComparator().compare(scope, [failed_event])
        self.assertEqual(len(alerts_failed), 1)
        self.assertEqual(alerts_failed[0].severity, "high")
        self.assertIn("execution failed with exit_code=1", alerts_failed[0].reason)

    def test_unconstrained_destructive_failure_downgraded_to_medium(self) -> None:
        # Without explicit prompt constraints, successful destructive is high, failed is medium
        scope = SessionScope(task_text="Investigate performance logs")
        failed_event = ObservedEvent(
            function="session:test",
            event_type="mutation",
            target="rm -rf /var/log/app",
            metadata={"command": "rm -rf /var/log/app", "success": False, "exit_code": 127},
        )
        alerts = MutationComparator().compare(scope, [failed_event])
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].severity, "medium")
        self.assertIn("execution failed with exit_code=127", alerts[0].reason)


if __name__ == "__main__":
    unittest.main()
