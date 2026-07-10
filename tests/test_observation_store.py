"""Tests for selfbull.observation_store — SELFBULL-002 append-only JSONL.

Standard library only. Run: python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from selfbull.observation_parser import build_envelope, parse_observation  # noqa: E402
from selfbull.observation_store import (  # noqa: E402
    ObservationStore,
    ObservationStoreError,
    record_hash,
)

NOW = datetime(2026, 7, 10, 16, 0, 0, tzinfo=timezone.utc)


def make_envelope(**overrides):
    row = {
        "timestamp_et": "2026-07-09 09:35:00",
        "symbol": "SPY",
        "last_price": "500.25",
        "bid": "500.24",
        "ask": "500.26",
        "session": "core",
        "source": "webull_browser_manual",
        "notes": "FICTIONAL test row",
    }
    row.update(overrides)
    parsed = parse_observation(row, now=NOW)
    return parsed, build_envelope(parsed).to_json_dict()


class TestAppendOnlyStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "nested" / "observations.jsonl"
        self.store = ObservationStore(self.path)

    def test_valid_ingest_appends_one_jsonl_row(self):
        _, envelope = make_envelope()
        receipt = self.store.append(envelope)
        self.assertTrue(self.path.exists())
        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0]), envelope)
        self.assertEqual(receipt.symbol, "SPY")
        self.assertEqual(receipt.source, "webull_browser_manual")
        self.assertEqual(receipt.validation_status, "valid")
        self.assertEqual(receipt.observed_at, "2026-07-09T09:35:00-04:00")
        self.assertTrue(receipt.receipt_id.startswith("obs-"))
        self.assertEqual(len(receipt.record_hash), 64)

    def test_dry_run_writes_nothing(self):
        _, envelope = make_envelope()
        receipt = self.store.append(envelope, dry_run=True)
        self.assertFalse(self.path.exists())
        self.assertEqual(receipt.record_hash, record_hash(envelope))
        self.assertEqual(self.store.count(), 0)

    def test_invalid_record_is_refused_and_writes_nothing(self):
        _, envelope = make_envelope(last_price="")  # invalid: required field
        with self.assertRaises(ObservationStoreError):
            self.store.append(envelope)
        self.assertFalse(self.path.exists())

    def test_conflicted_record_is_refused(self):
        _, envelope = make_envelope(spread="9.99")  # contradicts ask-bid
        with self.assertRaises(ObservationStoreError):
            self.store.append(envelope)
        self.assertFalse(self.path.exists())

    def test_repeated_ingest_never_rewrites_prior_rows(self):
        _, first = make_envelope()
        self.store.append(first)
        first_line = self.path.read_text(encoding="utf-8").splitlines()[0]
        _, second = make_envelope(symbol="QQQ", last_price="430.80",
                                  bid="430.78", ask="430.82")
        self.store.append(second)
        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], first_line)  # byte-identical, never rewritten
        self.assertEqual(self.store.count(), 2)

    def test_record_hash_is_deterministic(self):
        _, envelope = make_envelope()
        h1 = record_hash(envelope)
        h2 = record_hash(json.loads(json.dumps(envelope)))
        self.assertEqual(h1, h2)
        r1 = self.store.append(envelope, dry_run=True)
        r2 = self.store.append(envelope, dry_run=True)
        self.assertEqual(r1.record_hash, r2.record_hash)
        self.assertNotEqual(r1.receipt_id, r2.receipt_id)

    def test_execution_authority_true_is_refused(self):
        _, envelope = make_envelope()
        envelope["evidence"]["execution_authority"] = True
        with self.assertRaises(ObservationStoreError):
            self.store.append(envelope)
        self.assertFalse(self.path.exists())

    def test_non_serializable_record_is_refused(self):
        _, envelope = make_envelope()
        envelope["evidence"]["bad"] = float("nan")
        with self.assertRaises(ObservationStoreError):
            self.store.append(envelope)
        self.assertFalse(self.path.exists())

    def test_stored_output_contains_no_secret_markers(self):
        _, envelope = make_envelope()
        receipt = self.store.append(envelope)
        stored = self.path.read_text(encoding="utf-8")
        receipt_text = json.dumps(receipt.to_json_dict())
        for marker in ("xoxb-", "xapp-", "app_key_secret", "app_secret",
                       "password", "Bearer ", "-----BEGIN"):
            self.assertNotIn(marker, stored, marker)
            self.assertNotIn(marker, receipt_text, marker)
        # No environment values leak into rows or receipts.
        for value in os.environ.values():
            if len(value) >= 16:
                self.assertNotIn(value, stored)


if __name__ == "__main__":
    unittest.main()
