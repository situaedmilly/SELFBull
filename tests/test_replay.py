"""Tests for SELFBULL-003 retrospective replay."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from selfbull.observation_normalizer import normalize_observation  # noqa: E402
from selfbull.replay import replay_ledger  # noqa: E402
from selfbull.snapshot_ledger import SnapshotLedger  # noqa: E402


def raw_observation(observation_id, observed_at, recorded_at, price):
    return {
        "observation_id": observation_id,
        "observed_at": observed_at,
        "recorded_at": recorded_at,
        "observer": "human",
        "source": {
            "platform": "webull",
            "surface": "browser",
            "account_context": "manual_view_only",
        },
        "instrument": {"symbol": "SPY", "asset_class": "equity"},
        "market_state": {"last_price": price},
    }


class TestReplay(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = SnapshotLedger(Path(self.tmp.name) / "observations.jsonl")

    def test_replay_reconstructs_exact_chronology(self):
        first = normalize_observation(
            raw_observation("selfbull-obs-test-001", "2026-07-10T18:30:00Z", "2026-07-10T18:31:12Z", 632.14)
        )
        second = normalize_observation(
            raw_observation("selfbull-obs-test-002", "2026-07-10T18:35:00Z", "2026-07-10T18:35:22Z", 633.0)
        )

        self.ledger.append_observation(first)
        self.ledger.append_observation(second)
        frames = replay_ledger(self.ledger)

        self.assertEqual([frame["observation_id"] for frame in frames], [first.observation_id, second.observation_id])
        self.assertEqual(frames[0]["observed_at"], "2026-07-10T18:30:00Z")
        self.assertEqual(frames[1]["recorded_at"], "2026-07-10T18:35:22Z")
        self.assertEqual(frames[0]["deltas"], [])
        self.assertEqual(frames[1]["deltas"][0]["delta_type"], "price_changed")

    def test_replay_includes_validation_failures_without_prediction(self):
        self.ledger.append_validation_failure(
            raw_observation={"observation_id": "selfbull-obs-bad", "source": {}},
            errors=["source.account_context is required"],
            recorded_at="2026-07-10T18:40:00Z",
        )

        frames = replay_ledger(self.ledger)

        self.assertEqual(frames[0]["entry_type"], "validation_failure")
        self.assertEqual(frames[0]["record"]["validation_errors"], ["source.account_context is required"])
        self.assertNotIn("prediction", str(frames[0]).lower())


if __name__ == "__main__":
    unittest.main()
