"""Tests for selfbull.contracts — vocabulary correctness and envelope shape.

Standard library only. Run: python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from selfbull.contracts import (  # noqa: E402
    PreparedOrderIntent, TransportStatus, WebullInstrumentType, WebullOrderSide,
    WebullOrderStatus, WebullOrderTIF, WebullOrderType,
)

TS = "2026-07-09T00:00:00+00:00"


class TestVocabularyMatchesSDK(unittest.TestCase):
    """Guarantee #18: official Webull values used in contracts match the
    cited SDK source, not an earlier documentation-page assumption."""

    def test_order_side_values(self):
        self.assertEqual({m.value for m in WebullOrderSide}, {"BUY", "SELL", "SHORT"})

    def test_instrument_type_has_no_equity_member(self):
        names = {m.name for m in WebullInstrumentType}
        self.assertNotIn("EQUITY", names)
        self.assertIn("STOCK", names)

    def test_order_status_has_no_working_member(self):
        names = {m.name for m in WebullOrderStatus}
        self.assertNotIn("WORKING", names)
        self.assertIn("SUBMITTED", names)

    def test_order_type_has_no_limit_on_open_member(self):
        names = {m.name for m in WebullOrderType}
        self.assertNotIn("LIMIT_ON_OPEN", names)
        self.assertIn("MARKET_ON_OPEN", names)

    def test_order_tif_values(self):
        self.assertEqual({m.value for m in WebullOrderTIF}, {"DAY", "GTC", "IOC"})


class TestTransportStatusHasNoLiveMember(unittest.TestCase):
    def test_only_three_members(self):
        names = {m.name for m in TransportStatus}
        self.assertEqual(names, {"SIMULATED", "BLOCKED", "UNAVAILABLE"})

    def test_no_live_or_submitted_member(self):
        names = {m.name.lower() for m in TransportStatus}
        for forbidden in ("live", "submitted", "transmitted", "executed"):
            self.assertNotIn(forbidden, names)


class TestPreparedOrderIntent(unittest.TestCase):
    def _intent(self, **overrides):
        base = dict(
            broker="webull", instrument="AAPL", asset_class=WebullInstrumentType.STOCK,
            side=WebullOrderSide.BUY, order_type=WebullOrderType.MARKET, quantity=1,
            time_in_force=WebullOrderTIF.DAY, transport_status=TransportStatus.SIMULATED,
            created_at=TS,
        )
        base.update(overrides)
        return PreparedOrderIntent(**base)

    def test_is_json_serializable(self):
        intent = self._intent()
        blob = json.dumps(intent.to_json_dict())
        self.assertIn("AAPL", blob)

    def test_execution_authority_always_false(self):
        intent = self._intent()
        self.assertIs(intent.execution_authority, False)

    def test_caller_cannot_construct_execution_authority_true(self):
        with self.assertRaises(TypeError):
            self._intent(execution_authority=True)

    def test_human_approval_metadata_does_not_flip_authority(self):
        intent = self._intent(human_approval_id="human-approval-999")
        self.assertEqual(intent.human_approval_id, "human-approval-999")
        self.assertIs(intent.execution_authority, False)
        self.assertEqual(intent.transport_status, TransportStatus.SIMULATED)


if __name__ == "__main__":
    unittest.main()
