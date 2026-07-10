"""Tests for selfbull.manifest — Phase 1 status accuracy.

Standard library only. Run: python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from selfbull import manifest  # noqa: E402
from selfbull.adapter import STOP_ENV_VAR  # noqa: E402


class TestManifestAccuracy(unittest.TestCase):
    def test_manifest_phase_is_1(self):
        snap = manifest.status()
        self.assertEqual(snap["phase"], 1)

    def test_forbidden_capabilities_cover_execution_verbs(self):
        snap = manifest.status()
        for verb in ("order placement", "cancellation", "replacement", "transfer", "login"):
            self.assertIn(verb, snap["forbidden_capabilities"])

    def test_allowed_capabilities_cover_phase1_scope(self):
        snap = manifest.status()
        self.assertIn("paper/simulated order object creation", snap["allowed_capabilities"])

    def test_live_transport_reported_unavailable(self):
        snap = manifest.status()
        self.assertFalse(snap["live_transport_available"])
        self.assertFalse(snap["live_transport_enabled"])


class TestManifestKillSwitchReporting(unittest.TestCase):
    def tearDown(self):
        os.environ.pop(STOP_ENV_VAR, None)

    def test_kill_switch_reflected_in_status(self):
        os.environ[STOP_ENV_VAR] = "1"
        snap = manifest.status()
        self.assertTrue(snap["kill_switch_active"])


class TestManifestNeverLeaksSecretValue(unittest.TestCase):
    def test_status_json_never_contains_fake_secret(self):
        os.environ["SELFBULL_WEBULL_APP_KEY_ID"] = "LEAKTESTID1234"
        os.environ["SELFBULL_WEBULL_APP_KEY_SECRET"] = "LEAK-TEST-SECRET-VALUE"
        try:
            blob = json.dumps(manifest.status())
            self.assertNotIn("LEAK-TEST-SECRET-VALUE", blob)
        finally:
            os.environ.pop("SELFBULL_WEBULL_APP_KEY_ID", None)
            os.environ.pop("SELFBULL_WEBULL_APP_KEY_SECRET", None)


if __name__ == "__main__":
    unittest.main()
