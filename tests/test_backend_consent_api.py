import unittest

from backend.app import (
    app,
    consent_manager,
    capture_adapter,
    workflow_handoff,
)


class TestBackendConsentAPI(unittest.TestCase):

    def setUp(self):
        consent_manager.withdraw_consent()
        workflow_handoff.clear()
        self.client = app.test_client()

    def tearDown(self):
        consent_manager.withdraw_consent()
        workflow_handoff.clear()

    def test_consent_enable_and_withdraw_clears_state(self):
        # Consent and capture must start disabled.
        self.assertFalse(consent_manager.consent_enabled)
        self.assertFalse(capture_adapter.opt_in)

        response = self.client.get("/api/consent")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["consent_enabled"])

        # Enable consent through the actual API.
        response = self.client.post("/api/consent/enable")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["consent_enabled"])
        self.assertTrue(consent_manager.consent_enabled)
        self.assertTrue(capture_adapter.opt_in)

        # Add representative in-memory state.
        consent_manager.add_observation({"content": "synthetic test"})
        workflow_handoff._pending_proposals.append(object())
        workflow_handoff._approved_proposals.append(object())
        workflow_handoff._rejected_proposals.append(object())

        # Withdraw consent through the actual API.
        response = self.client.post("/api/consent/withdraw")
        self.assertEqual(response.status_code, 200)

        result = response.get_json()
        self.assertEqual(result["status"], "success")
        self.assertFalse(result["consent_enabled"])

        # Verify capture and consent are disabled.
        self.assertFalse(consent_manager.consent_enabled)
        self.assertFalse(capture_adapter.opt_in)

        # Verify all pending context and proposal state is cleared.
        self.assertEqual(consent_manager.get_pending_observations(), [])
        self.assertEqual(consent_manager._pending_observations, [])
        self.assertEqual(workflow_handoff.get_pending(), [])
        self.assertEqual(workflow_handoff.get_approved(), [])
        self.assertEqual(workflow_handoff.get_rejected(), [])


if __name__ == "__main__":
    unittest.main()
