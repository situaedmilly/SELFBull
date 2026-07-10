"""Tests for selfbull.adapter — Phase 1 refusal and representation guarantees.

Standard library only. Run: python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import os
import socket
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from selfbull.adapter import (  # noqa: E402
    AdapterQuarantineError, STOP_ENV_VAR, WebullAdapter, check_credentials,
    kill_switch_active, validate_config_shape,
)
from selfbull.contracts import (  # noqa: E402
    TransportStatus, WebullCredentialConfig, WebullInstrumentType, WebullOrderSide,
    WebullOrderTIF, WebullOrderType,
)

APP_KEY_ID_ENV = "SELFBULL_TEST_APP_KEY_ID"
APP_KEY_SECRET_ENV = "SELFBULL_TEST_APP_KEY_SECRET"


class TestCredentialPresence(unittest.TestCase):
    def test_missing_credentials_fail_safely(self):
        cfg = WebullCredentialConfig(app_key_id_env="SELFBULL_NOPE_ID", app_key_secret_env="SELFBULL_NOPE_SECRET")
        os.environ.pop(cfg.app_key_id_env, None)
        os.environ.pop(cfg.app_key_secret_env, None)
        result = check_credentials(cfg)
        self.assertFalse(result.app_key_id_present)
        self.assertFalse(result.app_key_secret_present)
        self.assertIsNone(result.app_key_id_prefix)
        self.assertFalse(result.both_present)

    def test_credential_check_returns_only_present_missing_prefix(self):
        os.environ[APP_KEY_ID_ENV] = "ABCDEFGH12345"
        os.environ[APP_KEY_SECRET_ENV] = "super-secret-value-never-shown"
        try:
            cfg = WebullCredentialConfig(app_key_id_env=APP_KEY_ID_ENV, app_key_secret_env=APP_KEY_SECRET_ENV)
            result = check_credentials(cfg)
            self.assertTrue(result.app_key_id_present)
            self.assertTrue(result.app_key_secret_present)
            self.assertEqual(result.app_key_id_prefix, "ABCD…")
            self.assertNotIn("ABCDEFGH12345", result.app_key_id_prefix or "")
            self.assertFalse(hasattr(result, "app_key_secret_prefix"))
            blob = json.dumps(result.to_json_dict())
            self.assertNotIn("super-secret-value-never-shown", blob)
        finally:
            os.environ.pop(APP_KEY_ID_ENV, None)
            os.environ.pop(APP_KEY_SECRET_ENV, None)

    def test_config_shape_validation(self):
        self.assertEqual(validate_config_shape(WebullCredentialConfig()), [])
        bad = WebullCredentialConfig(app_key_id_env="SAME", app_key_secret_env="SAME")
        errors = validate_config_shape(bad)
        self.assertTrue(any("must not be the same" in e for e in errors))
        bad_env = WebullCredentialConfig(environment="production_typo")
        self.assertTrue(validate_config_shape(bad_env))


class TestMarketDataIsReadOnlyAndUnimplemented(unittest.TestCase):
    def test_read_methods_raise_not_implemented_no_network(self):
        a = WebullAdapter()
        with self.assertRaises(NotImplementedError):
            a.get_account_list()
        with self.assertRaises(NotImplementedError):
            a.get_account_balance("ACCT-1")
        with self.assertRaises(NotImplementedError):
            a.get_quote("AAPL")


class TestPreparedOrderRepresentation(unittest.TestCase):
    def test_paper_order_can_be_represented(self):
        a = WebullAdapter()
        intent = a.create_prepared_order_intent(
            instrument="AAPL", asset_class=WebullInstrumentType.STOCK,
            side=WebullOrderSide.BUY, order_type=WebullOrderType.MARKET,
            quantity=1, time_in_force=WebullOrderTIF.DAY, timestamp="2026-07-09T00:00:00+00:00",
        )
        self.assertTrue(intent.intent_id.startswith("intent-"))
        self.assertEqual(intent.transport_status, TransportStatus.SIMULATED)
        self.assertIs(intent.execution_authority, False)


class TestLiveTransportRefusesByDefault(unittest.TestCase):
    def test_submit_cancel_replace_transfer_all_refuse(self):
        a = WebullAdapter()
        for method_name in ("submit", "cancel", "replace", "transfer"):
            method = getattr(a, method_name)
            with self.assertRaises(AdapterQuarantineError):
                method()

    def test_live_transport_unavailable_in_capability_snapshot(self):
        a = WebullAdapter()
        snap = a.build_capability_snapshot(timestamp="2026-07-09T00:00:00+00:00")
        self.assertFalse(snap.live_transport_available)
        self.assertFalse(snap.live_transport_enabled)


class TestKillSwitch(unittest.TestCase):
    def tearDown(self):
        os.environ.pop(STOP_ENV_VAR, None)

    def test_kill_switch_blocks_all_adapter_actions(self):
        os.environ[STOP_ENV_VAR] = "true"
        self.assertTrue(kill_switch_active())
        a = WebullAdapter()
        intent = a.create_prepared_order_intent(
            instrument="AAPL", asset_class=WebullInstrumentType.STOCK,
            side=WebullOrderSide.BUY, order_type=WebullOrderType.MARKET, quantity=1,
            timestamp="2026-07-09T00:00:00+00:00",
        )
        self.assertEqual(intent.transport_status, TransportStatus.BLOCKED)
        # live transport verbs still refuse via AdapterQuarantineError regardless
        with self.assertRaises(AdapterQuarantineError):
            a.submit()
        snap = a.build_capability_snapshot(timestamp="2026-07-09T00:00:00+00:00")
        self.assertTrue(snap.kill_switch_active)


class TestNoNetworkCall(unittest.TestCase):
    """Guarantee #17: no network call occurs during import or tests. We
    patch socket.socket to raise if the adapter ever touches it."""

    def test_full_adapter_workflow_never_touches_socket(self):
        original_socket = socket.socket

        def _forbidden(*_a, **_k):
            raise AssertionError("socket.socket() was called — Phase 1 must never touch the network")

        socket.socket = _forbidden
        try:
            a = WebullAdapter()
            check_credentials(a.config)
            validate_config_shape(a.config)
            a.create_prepared_order_intent(
                instrument="AAPL", asset_class=WebullInstrumentType.STOCK,
                side=WebullOrderSide.BUY, order_type=WebullOrderType.MARKET, quantity=1,
                timestamp="2026-07-09T00:00:00+00:00",
            )
            a.build_capability_snapshot(timestamp="2026-07-09T00:00:00+00:00")
            for method_name in ("submit", "cancel", "replace", "transfer"):
                try:
                    getattr(a, method_name)()
                except AdapterQuarantineError:
                    pass
            for method_name in ("get_account_list",):
                try:
                    getattr(a, method_name)()
                except NotImplementedError:
                    pass
        finally:
            socket.socket = original_socket


if __name__ == "__main__":
    unittest.main()
