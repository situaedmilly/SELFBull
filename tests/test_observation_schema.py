"""Tests for SELFBULL-003 structured observation schema."""
from __future__ import annotations

import os
import sys
import unittest
from dataclasses import FrozenInstanceError

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from selfbull.observation_schema import (  # noqa: E402
    MARKET_STATE_FIELDS,
    ObservationInstrument,
    ObservationSource,
    StructuredObservation,
)


def valid_observation(**overrides):
    values = {
        "observation_id": "selfbull-obs-test-001",
        "observed_at": "2026-07-10T18:30:00Z",
        "recorded_at": "2026-07-10T18:31:12Z",
        "observer": "human",
        "source": ObservationSource("webull", "browser", "manual_view_only"),
        "instrument": ObservationInstrument("SPY", "equity"),
        "market_state": {field: None for field in MARKET_STATE_FIELDS},
        "unknown_fields": [],
        "notes": None,
    }
    values["market_state"]["last_price"] = 632.14
    values.update(overrides)
    return StructuredObservation(**values)


class TestObservationSchema(unittest.TestCase):
    def test_execution_authority_is_false_and_not_constructor_argument(self):
        obs = valid_observation()
        self.assertIs(obs.execution_authority, False)
        self.assertIs(obs.to_json_dict()["execution_authority"], False)
        with self.assertRaises(TypeError):
            StructuredObservation(  # type: ignore[call-arg]
                observed_at="2026-07-10T18:30:00Z",
                recorded_at="2026-07-10T18:31:12Z",
                observer="human",
                source=ObservationSource("webull", "browser", "manual_view_only"),
                instrument=ObservationInstrument("SPY", "equity"),
                market_state={field: None for field in MARKET_STATE_FIELDS},
                execution_authority=True,
            )
        with self.assertRaises(FrozenInstanceError):
            obs.execution_authority = True  # type: ignore[misc]

    def test_missing_market_values_remain_null(self):
        obs = valid_observation(market_state={field: None for field in MARKET_STATE_FIELDS})
        payload = obs.to_json_dict()
        for field in MARKET_STATE_FIELDS:
            self.assertIsNone(payload["market_state"][field])


if __name__ == "__main__":
    unittest.main()
