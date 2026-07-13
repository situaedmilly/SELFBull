from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import FrozenInstanceError, replace
from unittest import TestCase

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import selfbull.snapshot_receipt_admission as admission_module  # noqa: E402
from selfbull.snapshot_receipt_admission import (  # noqa: E402
    AdmissionRefusal,
    FICTIONAL_FORMATTER_SHAPE_ID,
    FICTIONAL_RESULT_CONTAINER_TYPE,
    FICTIONAL_SOURCE_PACKAGE,
    FICTIONAL_SOURCE_PACKAGE_VERSION,
    RawWitnessReference,
    ScrubbedSnapshotDerivative,
    TransportReceipt,
    admit_formatted_snapshot,
    register_human_approved_derivative,
)


def _transport(**overrides):
    values = {
        "transport_receipt_id": "transport-001",
        "capture_session_id": "capture-001",
        "transport_plane": "webull_mcp_custom_composition",
        "tool_name": "get_stock_snapshot",
        "visible_tool_names": ("get_stock_snapshot",),
        "canonical_argument_field_names": ("symbol",),
        "admitted_argument_field_names": ("symbols",),
        "optional_arguments_forwarded": False,
        "broker_request_budget": 1,
        "broker_requests_executed": 1,
        "lifecycle_status": "CLOSED",
        "custody_status": "RAW_DESTROYED",
        "invocation_completed": True,
        "result_container_type": "CallToolResult",
        "result_payload_class": "formatted_text",
        "authentication_error_present": False,
        "entitlement_error_present": False,
        "protocol_error_present": False,
        "raw_output_committed": False,
        "raw_output_destroyed": True,
    }
    values.update(overrides)
    return TransportReceipt(**values)


def _raw_reference(**overrides):
    values = {
        "raw_reference_id": "raw-reference-001",
        "capture_session_id": "capture-001",
        "capture_started_at": "2026-07-13T01:00:00Z",
        "capture_recorded_at": "2026-07-13T01:00:01Z",
        "source_plane": "webull_mcp_custom_composition",
        "tool_name": "get_stock_snapshot",
        "raw_destroyed": True,
        "destruction_verified": True,
    }
    values.update(overrides)
    return RawWitnessReference(**values)


def _content(**overrides):
    values = {
        "symbol": "SPY",
        "last_price": "501.25",
        "bid": "501.20",
        "ask": "501.30",
        "volume": "123456",
        "observed_at": "NULL",
        "market_status": "OPEN",
        "delayed": "false",
    }
    values.update(overrides)
    lines = ["FORMAT=FICTIONAL_STOCK_SNAPSHOT_V1"]
    lines.extend(f"{key}={values[key]}" for key in values)
    lines.append("END")
    return "\n".join(lines)


def _admit(**overrides):
    values = {
        "transport_receipt": _transport(),
        "raw_reference": _raw_reference(),
        "derivative_id": "derivative-001",
        "expected_symbol": "SPY",
        "source_package": FICTIONAL_SOURCE_PACKAGE,
        "source_package_version": FICTIONAL_SOURCE_PACKAGE_VERSION,
        "formatter_shape_id": FICTIONAL_FORMATTER_SHAPE_ID,
        "result_container_type": FICTIONAL_RESULT_CONTAINER_TYPE,
        "structured_content_result": _content(),
    }
    values.update(overrides)
    return admit_formatted_snapshot(**values)


class TestArtifactBoundaries(TestCase):
    def test_transport_receipt_is_value_free(self):
        receipt = _transport().to_dict()
        encoded = json.dumps(receipt).lower()
        self.assertNotIn("last_price", encoded)
        self.assertNotIn('"symbol": "spy"', encoded)
        self.assertNotIn("raw_response", encoded)
        self.assertFalse(receipt["execution_authority"])

    def test_transport_receipt_refuses_broader_authority(self):
        self.assertFalse(_transport(optional_arguments_forwarded=True).valid_for_snapshot_admission())
        self.assertFalse(_transport(broker_requests_executed=2).valid_for_snapshot_admission())
        self.assertFalse(_transport(visible_tool_names=("get_stock_snapshot", "create_watchlist")).valid_for_snapshot_admission())
        self.assertFalse(_transport(transport_plane="account").valid_for_snapshot_admission())

    def test_transport_receipt_requires_exact_runtime_types(self):
        self.assertFalse(_transport(broker_request_budget=True).valid_for_snapshot_admission())
        self.assertFalse(_transport(broker_requests_executed=True).valid_for_snapshot_admission())
        self.assertFalse(_transport(optional_arguments_forwarded=0).valid_for_snapshot_admission())
        self.assertFalse(_transport(invocation_completed=1).valid_for_snapshot_admission())
        self.assertFalse(_transport(raw_output_destroyed=1).valid_for_snapshot_admission())

    def test_invalid_transport_receipt_cannot_be_serialized(self):
        with self.assertRaises(ValueError):
            _transport(broker_requests_executed=True).to_dict()

    def test_raw_reference_is_non_content_and_non_fixture(self):
        reference = _raw_reference()
        self.assertTrue(reference.valid_for_snapshot_admission())
        self.assertFalse(reference.raw_content_retained)
        self.assertIsNone(reference.repository_path)
        self.assertIsNone(reference.fixture_id)

    def test_raw_reference_requires_aware_capture_times(self):
        outcome = _admit(raw_reference=_raw_reference(capture_recorded_at="local time"))
        self.assertEqual(outcome.failure_class, "RAW_REFERENCE_INVALID")

    def test_raw_reference_requires_boolean_flags_and_chronology(self):
        self.assertFalse(_raw_reference(raw_destroyed=1).valid_for_snapshot_admission())
        self.assertFalse(_raw_reference(destruction_verified=1).valid_for_snapshot_admission())
        self.assertFalse(
            _raw_reference(
                capture_started_at="2026-07-13T02:00:00Z",
                capture_recorded_at="2026-07-13T01:00:00Z",
            ).valid_for_snapshot_admission()
        )

    def test_invalid_raw_reference_cannot_be_serialized(self):
        with self.assertRaises(ValueError):
            _raw_reference(raw_destroyed=1).to_dict()

    def test_artifacts_are_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            _transport().tool_name = "other"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            _raw_reference().raw_destroyed = False  # type: ignore[misc]


class TestFictionalFormatterAdmission(TestCase):
    def test_valid_fictional_content_creates_candidate(self):
        outcome = _admit()
        self.assertIsInstance(outcome, ScrubbedSnapshotDerivative)
        self.assertEqual(outcome.instrument_symbol, "SPY")
        self.assertIsNone(outcome.observed_at)
        self.assertEqual(outcome.observed_at_source, "UNAVAILABLE")
        self.assertEqual(outcome.recorded_at, "2026-07-13T01:00:01Z")
        self.assertEqual(outcome.market_fields["last_price"], "501.25")
        self.assertEqual(outcome.market_fields["spread"], "0.10")
        self.assertEqual(outcome.human_review_status, "PENDING")
        self.assertIsNone(outcome.sha256_registration)
        self.assertFalse(outcome.fixture_admitted)
        self.assertFalse(outcome.execution_authority)

    def test_candidate_does_not_retain_raw_content(self):
        outcome = _admit()
        encoded = json.dumps(outcome.to_dict())
        self.assertNotIn("FORMAT=FICTIONAL", encoded)
        self.assertNotIn("501.20\n", encoded)
        self.assertNotIn("raw_content", encoded)

    def test_explicit_broker_timestamp_is_preserved(self):
        timestamp = "2026-07-13T01:00:00Z"
        outcome = _admit(structured_content_result=_content(observed_at=timestamp))
        self.assertIsInstance(outcome, ScrubbedSnapshotDerivative)
        self.assertEqual(outcome.observed_at, timestamp)
        self.assertEqual(outcome.observed_at_source, "BROKER_EXPLICIT")

    def test_unknown_real_package_version_fails_closed(self):
        outcome = _admit(source_package_version="1.1.6")
        self.assertEqual(outcome.failure_class, "UNSUPPORTED_PACKAGE_VERSION")

    def test_unknown_formatter_shape_fails_closed(self):
        outcome = _admit(formatter_shape_id="unwitnessed.real.shape")
        self.assertEqual(outcome.failure_class, "UNKNOWN_FORMATTER_SHAPE")

    def test_missing_structured_content_fails_closed(self):
        outcome = _admit(structured_content_result=None)
        self.assertEqual(outcome.failure_class, "STRUCTURED_CONTENT_MISSING")

    def test_wrong_result_container_fails_closed(self):
        outcome = _admit(result_container_type="dict")
        self.assertEqual(outcome.failure_class, "RESULT_CONTAINER_MISSING")

    def test_missing_line_fails_closed(self):
        content = _content().replace("volume=123456\n", "")
        outcome = _admit(structured_content_result=content)
        self.assertEqual(outcome.failure_class, "REQUIRED_FIELD_MISSING")

    def test_duplicate_or_reordered_fields_fail_closed(self):
        lines = _content().splitlines()
        lines.insert(2, lines[1])
        duplicate = _admit(structured_content_result="\n".join(lines))
        self.assertIn(duplicate.failure_class, {"REQUIRED_FIELD_MISSING", "AMBIGUOUS_FIELD"})

        lines = _content().splitlines()
        lines[1], lines[2] = lines[2], lines[1]
        reordered = _admit(structured_content_result="\n".join(lines))
        self.assertEqual(reordered.failure_class, "AMBIGUOUS_FIELD")

    def test_symbol_mismatch_fails_closed(self):
        outcome = _admit(structured_content_result=_content(symbol="QQQ"))
        self.assertEqual(outcome.failure_class, "SYMBOL_MISMATCH")

    def test_unsafe_expected_symbol_fails_closed(self):
        outcome = _admit(
            expected_symbol="SPY secret",
            structured_content_result=_content(symbol="SPY secret"),
        )
        self.assertEqual(outcome.failure_class, "SYMBOL_MISMATCH")

    def test_invalid_numeric_and_boolean_values_fail_closed(self):
        for content in (
            _content(last_price="nan"),
            _content(bid="-1"),
            _content(bid="502", ask="501"),
            _content(volume="1.5"),
            _content(delayed="maybe"),
        ):
            with self.subTest(content=content):
                outcome = _admit(structured_content_result=content)
                self.assertEqual(outcome.failure_class, "VALUE_TYPE_INVALID")

    def test_ambiguous_timestamp_fails_closed(self):
        outcome = _admit(structured_content_result=_content(observed_at="local time"))
        self.assertEqual(outcome.failure_class, "TIMESTAMP_UNAVAILABLE")

    def test_secret_and_identity_patterns_fail_closed_without_reproduction(self):
        secret_value = "access_token=fictional-sensitive-value"
        secret = _admit(structured_content_result=_content(market_status=secret_value))
        self.assertEqual(secret.failure_class, "SECRET_PATTERN_PRESENT")
        self.assertNotIn("fictional-sensitive-value", json.dumps(secret.to_dict()))

        identity = _admit(structured_content_result=_content(market_status="account_id=123"))
        self.assertEqual(identity.failure_class, "IDENTITY_PATTERN_PRESENT")
        self.assertNotIn("123", json.dumps(identity.to_dict()))

    def test_forbidden_authority_vocabulary_fails_closed(self):
        outcome = _admit(structured_content_result=_content(market_status="order"))
        self.assertEqual(outcome.failure_class, "AMBIGUOUS_FIELD")

    def test_transport_and_raw_reference_must_link(self):
        outcome = _admit(raw_reference=_raw_reference(capture_session_id="other-session"))
        self.assertEqual(outcome.failure_class, "RAW_REFERENCE_INVALID")

    def test_artifact_identities_must_be_safe_and_distinct(self):
        unsafe = _admit(derivative_id="access_token=unsafe")
        self.assertEqual(unsafe.failure_class, "VALUE_TYPE_INVALID")
        self.assertNotIn("unsafe", json.dumps(unsafe.to_dict()))

        duplicate = _admit(derivative_id="transport-001")
        self.assertEqual(duplicate.failure_class, "VALUE_TYPE_INVALID")

    def test_unsupported_metadata_is_not_echoed(self):
        outcome = _admit(source_package_version="access_token=fictional-sensitive-value")
        encoded = json.dumps(outcome.to_dict())
        self.assertEqual(outcome.failure_class, "UNSUPPORTED_PACKAGE_VERSION")
        self.assertNotIn("fictional-sensitive-value", encoded)
        self.assertIn("UNSUPPORTED", encoded)

    def test_oversized_content_fails_closed(self):
        outcome = _admit(structured_content_result="x" * 10_001)
        self.assertEqual(outcome.failure_class, "VALUE_TYPE_INVALID")

    def test_invalid_transport_never_parses(self):
        outcome = _admit(transport_receipt=_transport(broker_requests_executed=0))
        self.assertEqual(outcome.failure_class, "TRANSPORT_RECEIPT_INVALID")

    def test_refusals_are_value_free_and_nonexecuting(self):
        outcome = _admit(formatter_shape_id="unknown")
        self.assertIsInstance(outcome, AdmissionRefusal)
        self.assertFalse(outcome.execution_authority)
        encoded = json.dumps(outcome.to_dict())
        self.assertNotIn("501.25", encoded)
        self.assertNotIn("SPY", encoded)


class TestHumanReviewAndHashing(TestCase):
    def test_hash_registration_requires_explicit_human_authorization(self):
        candidate = _admit()
        outcome = register_human_approved_derivative(
            candidate,
            human_review_authorized=False,
        )
        self.assertEqual(outcome.failure_class, "HUMAN_REVIEW_REQUIRED")

    def test_approved_derivative_gets_stable_non_self_referential_hash(self):
        candidate = _admit()
        first = register_human_approved_derivative(candidate, human_review_authorized=True)
        second = register_human_approved_derivative(candidate, human_review_authorized=True)
        self.assertIsInstance(first, ScrubbedSnapshotDerivative)
        self.assertEqual(first.human_review_status, "APPROVED")
        self.assertEqual(first.sha256_registration, second.sha256_registration)
        self.assertEqual(len(first.sha256_registration), 64)
        self.assertFalse(first.fixture_admitted)
        self.assertFalse(first.execution_authority)

        canonical = json.dumps(
            first.to_dict(include_hash=False),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        expected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self.assertEqual(first.sha256_registration, expected_hash)

    def test_human_authorization_requires_exact_boolean_and_pending_candidate(self):
        candidate = _admit()
        nonboolean = register_human_approved_derivative(
            candidate,
            human_review_authorized=1,
        )
        self.assertEqual(nonboolean.failure_class, "HUMAN_REVIEW_REQUIRED")

        approved = register_human_approved_derivative(
            candidate,
            human_review_authorized=True,
        )
        repeated = register_human_approved_derivative(
            approved,
            human_review_authorized=True,
        )
        self.assertEqual(repeated.failure_class, "HUMAN_REVIEW_REQUIRED")

    def test_market_fields_mapping_is_immutable(self):
        candidate = _admit()
        with self.assertRaises(TypeError):
            candidate.market_fields["last_price"] = "0"  # type: ignore[index]

    def test_direct_derivative_broadening_is_refused(self):
        candidate = _admit()
        with self.assertRaises(ValueError):
            replace(candidate, market_fields={**candidate.market_fields, "recommendation": "BUY"})

    def test_derivative_construction_and_replace_are_sealed(self):
        candidate = _admit()
        with self.assertRaises(ValueError):
            replace(candidate)

    def test_defense_in_depth_revalidates_market_values_and_metadata(self):
        candidate = _admit()
        with self.assertRaises(ValueError):
            replace(
                candidate,
                market_fields={**candidate.market_fields, "last_price": "not-a-number"},
                _construction_seal=admission_module._DERIVATIVE_CONSTRUCTION_SEAL,
            )
        with self.assertRaises(ValueError):
            replace(
                candidate,
                null_field_names=("fictional-sensitive-marker",),
                _construction_seal=admission_module._DERIVATIVE_CONSTRUCTION_SEAL,
            )

    def test_approved_content_cannot_change_with_stale_hash(self):
        candidate = _admit()
        approved = register_human_approved_derivative(
            candidate,
            human_review_authorized=True,
        )
        with self.assertRaises(ValueError):
            replace(
                approved,
                market_fields={**approved.market_fields, "last_price": "999.99"},
                _construction_seal=admission_module._DERIVATIVE_CONSTRUCTION_SEAL,
            )

    def test_approved_derivative_rechecks_hash_before_serialization(self):
        candidate = _admit()
        approved = register_human_approved_derivative(
            candidate,
            human_review_authorized=True,
        )
        object.__setattr__(approved, "sha256_registration", "0" * 64)
        with self.assertRaises(ValueError):
            approved.to_dict()


if __name__ == "__main__":
    import unittest

    unittest.main()
