import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import pairing


class PairingManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp_dir.name)
        self.patcher = patch("pairing._data_dir", return_value=self.directory)
        self.patcher.start()
        self.manager = pairing.PairingManager()
        self.device_id = str(uuid.uuid4())

    def tearDown(self):
        self.patcher.stop()
        self.temp_dir.cleanup()

    def test_request_requires_desktop_approval(self):
        result = self.manager.request_pairing(self.device_id, "My phone")
        self.assertEqual(result["status"], "pending")
        self.assertFalse(self.manager.authenticate(""))

        pending = self.manager.pending_requests()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["device_name"], "My phone")

    def test_approved_session_token_is_one_time_delivered(self):
        result = self.manager.request_pairing(self.device_id, "My phone")
        self.assertTrue(self.manager.approve(result["request_id"]))
        delivered = self.manager.pairing_status(result["request_id"])
        self.assertEqual(delivered["status"], "approved")
        token = delivered["session_token"]
        self.assertTrue(self.manager.authenticate(token))
        self.assertEqual(
            self.manager.pairing_status(result["request_id"])["session_token"],
            token,
        )

    def test_trusted_device_can_be_auto_approved(self):
        request = self.manager.request_pairing(self.device_id, "My phone")
        self.assertTrue(
            self.manager.approve(request["request_id"], trust_device=True)
        )
        self.manager.set_auto_allow_trusted(True)

        restored = pairing.PairingManager()
        next_request = restored.request_pairing(self.device_id, "My phone")
        self.assertEqual(next_request["status"], "approved")
        self.assertTrue(restored.authenticate(next_request["session_token"]))

    def test_denied_request_does_not_issue_session(self):
        request = self.manager.request_pairing(self.device_id, "Unknown device")
        self.assertTrue(self.manager.deny(request["request_id"]))
        self.assertEqual(
            self.manager.pairing_status(request["request_id"]),
            {"status": "denied"},
        )


if __name__ == "__main__":
    unittest.main()
