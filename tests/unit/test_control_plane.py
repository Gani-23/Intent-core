import unittest
from fastapi.testclient import TestClient
from lsa.api.main import app

class TestControlPlaneEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_target_profiles_lifecycle(self):
        # 1. List target profiles (seeded)
        res = self.client.get("/maintenance/live-workload-target-profiles")
        self.assertEqual(res.status_code, 200)
        profiles = res.json()
        self.assertTrue(len(profiles) >= 3)
        names = [p["name"] for p in profiles]
        self.assertIn("express-pair", names)
        self.assertIn("production-gateway", names)

        # 2. Upsert custom profile
        custom_profile = {
            "name": "test-unit-profile",
            "approved_target_base_url": "https://api.approved.local",
            "drift_target_base_url": "https://api.drift.local",
            "description": "Unit test profile",
            "enabled": True,
        }
        res_post = self.client.post("/maintenance/live-workload-target-profiles", json=custom_profile)
        self.assertEqual(res_post.status_code, 200)
        self.assertEqual(res_post.json()["name"], "test-unit-profile")

        # 3. Target profile actions
        res_val = self.client.post("/maintenance/live-workload-target-profiles/test-unit-profile/validate")
        self.assertEqual(res_val.status_code, 200)
        self.assertEqual(res_val.json()["status"], "passed")

        res_drift = self.client.post("/maintenance/live-workload-target-profiles/test-unit-profile/drift-proof")
        self.assertEqual(res_drift.status_code, 200)
        self.assertEqual(res_drift.json()["status"], "verified")

        res_canary = self.client.post("/maintenance/live-workload-target-profiles/test-unit-profile/canary-verify")
        self.assertEqual(res_canary.status_code, 200)
        self.assertEqual(res_canary.json()["verdict"], "CLEAN — SAFE FOR PROMOTION")

        # 4. Activity and explanation
        res_act = self.client.get("/maintenance/live-workload-target-profiles/test-unit-profile/activity")
        self.assertEqual(res_act.status_code, 200)
        self.assertEqual(res_act.json()["profile_name"], "test-unit-profile")

        res_exp = self.client.get("/maintenance/live-workload-target-profiles/test-unit-profile/explanation")
        self.assertEqual(res_exp.status_code, 200)
        self.assertIn("Routing Integrity Analysis", res_exp.json()["title"])

        # 5. Delete profile
        res_del = self.client.delete("/maintenance/live-workload-target-profiles/test-unit-profile")
        self.assertEqual(res_del.status_code, 200)
        self.assertTrue(res_del.json()["deleted"])

    def test_governance_queues_and_readiness(self):
        # Deployment readiness
        res_readiness = self.client.get("/maintenance/control-plane-deployment-readiness")
        self.assertEqual(res_readiness.status_code, 200)
        data = res_readiness.json()
        self.assertIn("ready", data)
        self.assertIn("runtime_validation", data)
        self.assertIn("live_workload_target_validation", data)
        self.assertIn("runtime_validation_change_control_requests", data)
        self.assertTrue(len(data["runtime_validation_change_control_requests"]) > 0)

        # Owner team queue
        res_queue = self.client.get("/maintenance/control-plane-deployment-readiness/owner-team-queue")
        self.assertEqual(res_queue.status_code, 200)
        self.assertIn("requests", res_queue.json())

        # Runtime review queue (both aliases)
        res_rev1 = self.client.get("/maintenance/control-plane-runtime-review-queue")
        self.assertEqual(res_rev1.status_code, 200)
        res_rev2 = self.client.get("/maintenance/control-plane-runtime-validation-review-queue")
        self.assertEqual(res_rev2.status_code, 200)
        self.assertEqual(res_rev1.json()["total_reviews"], res_rev2.json()["total_reviews"])

        # Trust score
        res_trust = self.client.get("/maintenance/control-plane-trust-score")
        self.assertEqual(res_trust.status_code, 200)
        self.assertEqual(res_trust.json()["score"], 94)

        # Incident narrative (both aliases)
        res_nar1 = self.client.get("/incidents/control-plane-narrative")
        self.assertEqual(res_nar1.status_code, 200)
        res_nar2 = self.client.get("/maintenance/control-plane-incident-narrative")
        self.assertEqual(res_nar2.status_code, 200)

    def test_alert_rail_and_acknowledgement(self):
        res_alerts = self.client.get("/control-plane-alerts")
        self.assertEqual(res_alerts.status_code, 200)
        alerts = res_alerts.json()
        self.assertTrue(len(alerts) >= 3)
        target_alert = alerts[0]["alert_id"]

        # Acknowledge
        res_ack = self.client.post(
            f"/control-plane-alerts/{target_alert}/acknowledge",
            json={"acknowledgement_note": "Verified by test suite"}
        )
        self.assertEqual(res_ack.status_code, 200)
        self.assertEqual(res_ack.json()["status"], "acknowledged")

        # Emit alert
        res_emit = self.client.post("/maintenance/emit-control-plane-alerts")
        self.assertEqual(res_emit.status_code, 200)
        self.assertEqual(res_emit.json()["status"], "emitted")

    def test_proof_bundles_export_inspect_delete(self):
        res_list = self.client.get("/maintenance/live-workload-proof-bundles")
        self.assertEqual(res_list.status_code, 200)

        # Export
        res_exp = self.client.post(
            "/maintenance/live-workload-proof-bundles/export",
            json={"target_profile": "production-gateway"}
        )
        self.assertEqual(res_exp.status_code, 200)
        bundle_path = res_exp.json()["output_path"]

        # Inspect
        res_ins = self.client.post(
            "/maintenance/live-workload-proof-bundles/inspect",
            json={"path": bundle_path}
        )
        self.assertEqual(res_ins.status_code, 200)
        self.assertTrue(res_ins.json()["valid"])

        # Delete
        res_del = self.client.post(
            "/maintenance/live-workload-proof-bundles/delete",
            json={"path": bundle_path}
        )
        self.assertEqual(res_del.status_code, 200)
        self.assertTrue(res_del.json()["deleted"])
