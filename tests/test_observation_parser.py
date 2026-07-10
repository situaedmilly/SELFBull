"""Tests for selfbull.observation_parser — SELFBULL-002 manual intake.

Standard library only. Run: python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from selfbull.observation_parser import (  # noqa: E402
    CAPTURE_MODE,
    CONFLICTED,
    INVALID,
    MANUAL_SOURCE,
    VALID,
    build_envelope,
    parse_observation,
)

# A frozen "now" so future-timestamp checks are deterministic.
NOW = datetime(2026, 7, 10, 16, 0, 0, tzinfo=timezone.utc)


def valid_row(**overrides):
    row = {
        "timestamp_et": "2026-07-09 09:35:00",
        "symbol": "SPY",
        "last_price": "500.25",
        "day_open": "499.10",
        "day_high": "501.40",
        "day_low": "498.60",
        "previous_close": "498.90",
        "volume": "4200000",
        "relative_volume": "1.1",
        "bid": "500.24",
        "ask": "500.26",
        "spread": "0.02",
        "implied_volatility": "14.2",
        "expected_move": "3.5",
        "call_wall": "505",
        "put_wall": "495",
        "largest_call_volume_strike": "505",
        "largest_put_volume_strike": "495",
        "session": "core",
        "source": "webull_browser_manual",
        "notes": "FICTIONAL test row",
    }
    row.update(overrides)
    return row


class TestRequiredFields(unittest.TestCase):
    def test_valid_row_parses(self):
        parsed = parse_observation(valid_row(), now=NOW)
        self.assertEqual(parsed.validation_status, VALID)
        self.assertEqual(parsed.errors, [])
        self.assertEqual(parsed.normalized["symbol"], "SPY")
        self.assertEqual(parsed.normalized["last_price"], 500.25)

    def test_missing_last_price_fails(self):
        parsed = parse_observation(valid_row(last_price=""), now=NOW)
        self.assertEqual(parsed.validation_status, INVALID)
        self.assertTrue(any("last_price is required" in e for e in parsed.errors))

    def test_missing_symbol_fails(self):
        parsed = parse_observation(valid_row(symbol="  "), now=NOW)
        self.assertEqual(parsed.validation_status, INVALID)

    def test_missing_timestamp_is_never_replaced_with_now(self):
        parsed = parse_observation(valid_row(timestamp_et=""), now=NOW)
        self.assertEqual(parsed.validation_status, INVALID)
        self.assertIsNone(parsed.normalized["timestamp_et"])

    def test_missing_source_fails(self):
        parsed = parse_observation(valid_row(source=""), now=NOW)
        self.assertEqual(parsed.validation_status, INVALID)

    def test_wrong_source_fails(self):
        parsed = parse_observation(valid_row(source="webull_api"), now=NOW)
        self.assertEqual(parsed.validation_status, INVALID)
        self.assertTrue(any(MANUAL_SOURCE in e for e in parsed.errors))


class TestSymbolNormalization(unittest.TestCase):
    def test_symbol_normalizes_to_uppercase(self):
        parsed = parse_observation(valid_row(symbol="  spy "), now=NOW)
        self.assertEqual(parsed.normalized["symbol"], "SPY")
        self.assertEqual(parsed.validation_status, VALID)

    def test_unsafe_symbol_rejected(self):
        for bad in ("SP Y", "SPY;rm", "SP$Y", "../SPY", "S\tP"):
            parsed = parse_observation(valid_row(symbol=bad), now=NOW)
            self.assertEqual(parsed.validation_status, INVALID, bad)

    def test_index_like_symbol_preserved(self):
        parsed = parse_observation(valid_row(symbol="VIX"), now=NOW)
        self.assertEqual(parsed.normalized["symbol"], "VIX")
        self.assertEqual(parsed.validation_status, VALID)


class TestTimestamps(unittest.TestCase):
    def test_invalid_timestamp_fails(self):
        for bad in ("yesterday", "2026-13-45 09:00:00", "09:35", "2026/07/09"):
            parsed = parse_observation(valid_row(timestamp_et=bad), now=NOW)
            self.assertEqual(parsed.validation_status, INVALID, bad)

    def test_future_timestamp_fails(self):
        parsed = parse_observation(valid_row(timestamp_et="2027-01-01 09:30:00"), now=NOW)
        self.assertEqual(parsed.validation_status, INVALID)
        self.assertTrue(any("future" in e for e in parsed.errors))

    def test_normalized_to_iso8601_with_eastern_offset(self):
        parsed = parse_observation(valid_row(), now=NOW)
        # July → EDT, UTC-4.
        self.assertEqual(parsed.normalized["timestamp_et"], "2026-07-09T09:35:00-04:00")

    def test_winter_timestamp_gets_est_offset(self):
        parsed = parse_observation(valid_row(timestamp_et="2026-01-09 09:35:00"), now=NOW)
        self.assertEqual(parsed.normalized["timestamp_et"], "2026-01-09T09:35:00-05:00")

    def test_explicit_offset_is_respected(self):
        parsed = parse_observation(
            valid_row(timestamp_et="2026-07-09T09:35:00-04:00"), now=NOW
        )
        self.assertEqual(parsed.validation_status, VALID)


class TestNumericValidation(unittest.TestCase):
    def test_negative_price_fails(self):
        parsed = parse_observation(valid_row(last_price="-5.00"), now=NOW)
        self.assertEqual(parsed.validation_status, INVALID)

    def test_nan_and_infinity_fail(self):
        for bad in ("nan", "NaN", "inf", "-inf", "Infinity"):
            parsed = parse_observation(valid_row(last_price=bad), now=NOW)
            self.assertEqual(parsed.validation_status, INVALID, bad)

    def test_malformed_number_fails(self):
        parsed = parse_observation(valid_row(volume="lots"), now=NOW)
        self.assertEqual(parsed.validation_status, INVALID)

    def test_optional_blank_values_become_none(self):
        row = valid_row(
            volume="", relative_volume="", implied_volatility="",
            expected_move="", call_wall="", put_wall="",
            largest_call_volume_strike="", largest_put_volume_strike="",
            session="", notes="",
        )
        parsed = parse_observation(row, now=NOW)
        self.assertEqual(parsed.validation_status, VALID)
        for name in ("volume", "relative_volume", "implied_volatility",
                     "expected_move", "call_wall", "put_wall", "session", "notes"):
            self.assertIsNone(parsed.normalized[name], name)
        self.assertIn("volume", parsed.missing_fields)


class TestSpread(unittest.TestCase):
    def test_spread_calculated_when_bid_and_ask_exist(self):
        parsed = parse_observation(valid_row(spread=""), now=NOW)
        self.assertEqual(parsed.validation_status, VALID)
        self.assertAlmostEqual(parsed.normalized["spread"], 0.02)

    def test_spread_not_fabricated_without_bid_ask(self):
        parsed = parse_observation(valid_row(bid="", ask="", spread=""), now=NOW)
        self.assertEqual(parsed.validation_status, VALID)
        self.assertIsNone(parsed.normalized["spread"])

    def test_spread_contradiction_detected_and_supplied_value_preserved(self):
        parsed = parse_observation(valid_row(spread="0.50"), now=NOW)
        self.assertEqual(parsed.validation_status, CONFLICTED)
        self.assertTrue(any("contradicts" in e for e in parsed.errors))
        self.assertEqual(parsed.normalized["spread"], 0.50)  # never overwritten

    def test_matching_supplied_spread_is_not_a_conflict(self):
        parsed = parse_observation(valid_row(spread="0.02"), now=NOW)
        self.assertEqual(parsed.validation_status, VALID)


class TestRangeConsistency(unittest.TestCase):
    def test_last_price_outside_day_range_detected(self):
        parsed = parse_observation(
            valid_row(last_price="510.00", spread="", bid="", ask=""), now=NOW
        )
        self.assertEqual(parsed.validation_status, CONFLICTED)
        self.assertTrue(any("outside day range" in e for e in parsed.errors))

    def test_open_outside_day_range_detected(self):
        parsed = parse_observation(valid_row(day_open="600.00"), now=NOW)
        self.assertEqual(parsed.validation_status, CONFLICTED)

    def test_low_above_high_detected(self):
        parsed = parse_observation(
            valid_row(day_low="502.00", day_high="501.40", last_price="501.50",
                      day_open="501.45"), now=NOW
        )
        self.assertEqual(parsed.validation_status, CONFLICTED)


class TestEnvelope(unittest.TestCase):
    def test_envelope_is_json_serializable(self):
        parsed = parse_observation(valid_row(), now=NOW)
        envelope = build_envelope(parsed).to_json_dict()
        text = json.dumps(envelope, allow_nan=False)
        self.assertEqual(json.loads(text), envelope)

    def test_source_remains_webull_browser_manual(self):
        parsed = parse_observation(valid_row(), now=NOW)
        envelope = build_envelope(parsed).to_json_dict()
        self.assertEqual(envelope["source"], "webull_browser_manual")
        self.assertEqual(envelope["broker"], "webull")

    def test_capture_mode_is_manual_browser_observation(self):
        parsed = parse_observation(valid_row(), now=NOW)
        envelope = build_envelope(parsed).to_json_dict()
        self.assertEqual(envelope["evidence"]["capture_mode"], "MANUAL_BROWSER_OBSERVATION")
        self.assertEqual(CAPTURE_MODE, "MANUAL_BROWSER_OBSERVATION")

    def test_evidence_preserves_raw_input_and_validation_outcome(self):
        parsed = parse_observation(valid_row(spread="0.50"), now=NOW)
        envelope = build_envelope(parsed).to_json_dict()
        ev = envelope["evidence"]
        self.assertEqual(ev["validation_status"], CONFLICTED)
        self.assertEqual(ev["raw_input"]["spread"], "0.50")
        self.assertTrue(ev["validation_errors"])
        self.assertIn("missing_fields", ev)
        self.assertIs(ev["network_call"], False)

    def test_envelope_carries_required_contract_fields(self):
        parsed = parse_observation(valid_row(), now=NOW)
        envelope = build_envelope(parsed).to_json_dict()
        for key in ("schema_version", "broker", "observed_at", "instrument",
                    "quote", "session", "source", "freshness", "evidence"):
            self.assertIn(key, envelope)
        self.assertEqual(envelope["observed_at"], "2026-07-09T09:35:00-04:00")
        self.assertEqual(envelope["instrument"]["symbol"], "SPY")

    def test_no_execution_authority_can_appear_true(self):
        parsed = parse_observation(valid_row(), now=NOW)
        envelope = build_envelope(parsed).to_json_dict()
        text = json.dumps(envelope).replace(" ", "")
        self.assertNotIn('"execution_authority":true', text)


if __name__ == "__main__":
    unittest.main()
