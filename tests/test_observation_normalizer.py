"""Tests for SELFBULL-003 observation normalization and validation."""
from __future__ import annotations

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from selfbull.observation_normalizer import normalize_observation  # noqa: E402
from selfbull.observation_validator import validate_observation  # noqa: E402


class TestObservationNormalizer(unittest.TestCase):
    def test_valid_manual_observation_is_accepted(self):
        obs = normalize_observation(
            {
                "observation_id": "selfbull-obs-test-001",
                "observed_at": "2026-07-10T18:30:00Z",
                "recorded_at": "2026-07-10T18:31:12Z",
                "observer": "human",
                "source": {
                    "platform": "webull",
                    "surface": "browser",
                    "account_context": "manual_view_only",
                },
                "instrument": {"symbol": "spy", "asset_class": "equity"},
                "market_state": {"last_price": "632.14", "bid": "", "ask": None},
            }
        )

        self.assertEqual(obs.instrument.symbol, "SPY")
        self.assertEqual(obs.market_state["last_price"], 632.14)
        self.assertIsNone(obs.market_state["bid"])
        self.assertIsNone(obs.market_state["ask"])
        self.assertTrue(validate_observation(obs).valid)

    def test_missing_required_provenance_is_rejected(self):
        obs = normalize_observation(
            {
                "observation_id": "selfbull-obs-test-002",
                "observed_at": "2026-07-10T18:30:00Z",
                "recorded_at": "2026-07-10T18:31:12Z",
                "observer": "human",
                "source": {"platform": "webull", "surface": "browser"},
                "instrument": {"symbol": "SPY", "asset_class": "equity"},
                "market_state": {},
            }
        )

        result = validate_observation(obs)
        self.assertFalse(result.valid)
        self.assertIn("source.account_context is required", result.errors)

    def test_unknown_values_are_never_fabricated(self):
        obs = normalize_observation(
            {
                "observation_id": "selfbull-obs-test-003",
                "observed_at": "2026-07-10T18:30:00Z",
                "recorded_at": "2026-07-10T18:31:12Z",
                "observer": "human",
                "source": {
                    "platform": "webull",
                    "surface": "browser",
                    "account_context": "manual_view_only",
                },
                "instrument": {"symbol": "SPY", "asset_class": ""},
                "market_state": {},
            }
        )

        self.assertIsNone(obs.instrument.asset_class)
        for value in obs.market_state.values():
            self.assertIsNone(value)

    def test_missing_observation_id_gets_local_evidence_id(self):
        obs = normalize_observation(
            {
                "observed_at": "2026-07-10T18:30:00Z",
                "recorded_at": "2026-07-10T18:31:12Z",
                "observer": "human",
                "source": {
                    "platform": "webull",
                    "surface": "browser",
                    "account_context": "manual_view_only",
                },
                "instrument": {"symbol": "SPY", "asset_class": "equity"},
                "market_state": {},
            }
        )

        self.assertTrue(obs.observation_id.startswith("selfbull-obs-"))
        self.assertTrue(validate_observation(obs).valid)

    def test_mixed_string_integer_keys_do_not_raise(self):
        raw = {
            1: "malformed",
            "foo": "unknown",
            "observed_at": "2026-07-10T18:30:00Z",
            "recorded_at": "2026-07-10T18:31:12Z",
            "observer": "human",
            "source": {
                "platform": "webull",
                "surface": "browser",
                "account_context": "manual_view_only",
            },
            "instrument": {"symbol": "SPY", "asset_class": "equity"},
            "market_state": {},
        }

        obs = normalize_observation(raw)

        self.assertIn("non-string field keys are not permitted", obs.unknown_fields)
        self.assertEqual(obs.unknown_fields[-1], "non-string field keys are not permitted")
        self.assertIn("foo", obs.unknown_fields)
        self.assertEqual(raw[1], "malformed")

    def test_unknown_string_keys_remain_sorted(self):
        raw = {
            "zeta": "1",
            "alpha": "2",
            "observed_at": "2026-07-10T18:30:00Z",
            "recorded_at": "2026-07-10T18:31:12Z",
            "observer": "human",
            "source": {
                "platform": "webull",
                "surface": "browser",
                "account_context": "manual_view_only",
            },
            "instrument": {"symbol": "SPY", "asset_class": "equity"},
            "market_state": {},
        }

        obs = normalize_observation(raw)

        self.assertEqual(obs.unknown_fields, ["alpha", "zeta"])


if __name__ == "__main__":
    unittest.main()
