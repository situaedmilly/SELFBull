"""Tests for SELFBULL-003 append-only snapshot ledger."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from selfbull.observation_schema import MARKET_STATE_FIELDS  # noqa: E402
from selfbull.observation_normalizer import normalize_observation  # noqa: E402
from selfbull.snapshot_ledger import SnapshotLedger, SnapshotLedgerError  # noqa: E402


def raw_observation(observation_id="selfbull-obs-test-001", price=632.14):
    return {
        "observation_id": observation_id,
        "observed_at": "2026-07-10T18:30:00Z",
        "recorded_at": "2026-07-10T18:31:12Z",
        "observer": "human",
        "source": {
            "platform": "webull",
            "surface": "browser",
            "account_context": "manual_view_only",
        },
        "instrument": {"symbol": "SPY", "asset_class": "equity"},
        "market_state": {"last_price": price, **{field: None for field in MARKET_STATE_FIELDS if field != "last_price"}},
    }


class TestSnapshotLedger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "observations.jsonl"
        self.ledger = SnapshotLedger(self.path)

    def test_prior_records_cannot_be_overwritten(self):
        obs = normalize_observation(raw_observation())
        self.ledger.append_observation(obs)
        first = self.path.read_text(encoding="utf-8")
        self.ledger.append_observation(normalize_observation(raw_observation("selfbull-obs-test-002", 633.0)))
        second = self.path.read_text(encoding="utf-8")

        self.assertTrue(second.startswith(first))
        self.assertEqual(len(second.splitlines()), 2)

    def test_corrections_create_revision_records(self):
        original = normalize_observation(raw_observation())
        correction = normalize_observation(raw_observation("selfbull-obs-test-001-rev-001", 632.2))

        self.ledger.append_observation(original)
        receipt = self.ledger.append_revision(
            original_observation_id=original.observation_id,
            corrected_observation=correction,
            reason="manual correction from reviewed browser note",
        )
        entries = self.ledger.entries()

        self.assertEqual(receipt.entry_type, "revision")
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[1]["revision_of"], original.observation_id)
        self.assertEqual(entries[0]["observation_id"], original.observation_id)

    def test_correction_cannot_reuse_original_id(self):
        original = normalize_observation(raw_observation())
        self.ledger.append_observation(original)
        with self.assertRaises(SnapshotLedgerError):
            self.ledger.append_revision(
                original_observation_id=original.observation_id,
                corrected_observation=original,
                reason="bad correction",
            )


if __name__ == "__main__":
    unittest.main()
