"""Tests for SELFBULL-003 factual observation deltas."""
from __future__ import annotations

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from selfbull.observation_delta import FACTUAL_DELTA_TYPES, delta_dicts  # noqa: E402


class TestObservationDelta(unittest.TestCase):
    def test_delta_engine_reports_factual_changes_only(self):
        previous = {
            "market_state": {
                "last_price": 632.14,
                "spread": 0.02,
                "volume": 100,
                "open_interest": None,
            }
        }
        current = {
            "market_state": {
                "last_price": 633.0,
                "spread": 0.04,
                "volume": 150,
                "open_interest": 10,
            }
        }

        deltas = delta_dicts(previous, current)
        labels = {delta["delta_type"] for delta in deltas}

        self.assertIn("price_changed", labels)
        self.assertIn("spread_widened", labels)
        self.assertIn("volume_increased", labels)
        self.assertIn("field_became_available", labels)
        self.assertTrue(labels.issubset(set(FACTUAL_DELTA_TYPES)))

    def test_predictive_vocabulary_absent_from_delta_labels(self):
        forbidden = {"bullish", "bearish", "buy", "sell", "entry", "exit", "signal", "target", "prediction"}
        self.assertTrue(forbidden.isdisjoint(set(FACTUAL_DELTA_TYPES)))


if __name__ == "__main__":
    unittest.main()
