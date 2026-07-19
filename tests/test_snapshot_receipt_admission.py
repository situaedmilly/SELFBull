from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import os
import sys
from dataclasses import FrozenInstanceError, replace
from unittest import TestCase
from unittest.mock import patch

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
    WEBULL_MCP_FORMATTER_SHAPE_ID,
    WEBULL_MCP_HEADER,
    WEBULL_MCP_SOURCE_FILE_HASHES,
    WEBULL_MCP_SOURCE_PACKAGE,
    WEBULL_MCP_SOURCE_PACKAGE_VERSION,
    WEBULL_MCP_US_DISCLAIMER_LINE,
    admit_formatted_snapshot,
    register_human_approved_derivative,
)


_MISSING = object()

_GENERIC_SECRET_IDENTIFIER_MARKERS = (
    "token:fictional-sensitive-value",
    "api-token:fictional-sensitive-value",
    "api_token:fictional-sensitive-value",
    "secret:fictional-sensitive-value",
    "client-secret:fictional-sensitive-value",
    "client_secret:fictional-sensitive-value",
    "credential:fictional-sensitive-value",
    "credentials:fictional-sensitive-value",
    "service-credential:fictional-sensitive-value",
    "service_credential:fictional-sensitive-value",
    "password:fictional-sensitive-value",
    "user-password:fictional-sensitive-value",
    "user_password:fictional-sensitive-value",
)

_GENERIC_SECRET_CONTENT_MARKERS = (
    "token: fictional-sensitive-value",
    "token=fictional-sensitive-value",
    "api token: fictional-sensitive-value",
    "api-token=fictional-sensitive-value",
    "api_token = fictional-sensitive-value",
    "secret: fictional-sensitive-value",
    "client secret=fictional-sensitive-value",
    "client-secret: fictional-sensitive-value",
    "client_secret = fictional-sensitive-value",
    "credential: fictional-sensitive-value",
    "credentials=fictional-sensitive-value",
    "service credential: fictional-sensitive-value",
    "service-credential=fictional-sensitive-value",
    "service_credential = fictional-sensitive-value",
    "password: fictional-sensitive-value",
    "user password=fictional-sensitive-value",
    "user-password: fictional-sensitive-value",
    "user_password = fictional-sensitive-value",
)


class CallToolResult:
    """Offline model of the original low-level MCP result envelope."""

    def __init__(
        self,
        *,
        structured_content=_MISSING,
        is_error=False,
        content=None,
        meta=None,
    ):
        if structured_content is not _MISSING:
            self.structuredContent = structured_content
        if is_error is not _MISSING:
            self.isError = is_error
        self.content = [] if content is None else content
        self._meta = meta


CallToolResult.__module__ = "mcp.types"


class HostileAttributeObject:
    """Object whose sensitive attributes must never be inspected or rendered."""

    def __init__(self):
        object.__setattr__(self, "access_count", 0)

    def __getattribute__(self, name):
        if name in {
            "transport_receipt_id",
            "raw_reference_id",
            "capture_session_id",
            "derivative_id",
            "revision_of",
            "fixture_id",
            "parser_version",
            "schema_version",
            "instrument_symbol",
            "source_package",
            "source_package_version",
            "formatter_shape_id",
            "human_review_status",
            "sha256_registration",
        }:
            count = object.__getattribute__(self, "access_count")
            object.__setattr__(self, "access_count", count + 1)
            raise RuntimeError("hostile attribute detail")
        return object.__getattribute__(self, name)

    def __repr__(self):
        raise RuntimeError("hostile repr detail")

    def __str__(self):
        raise RuntimeError("hostile str detail")


class HostileTrustedEnvelope:
    """Trusted-type test double with one controlled hostile property."""

    def __init__(self, exception):
        self.exception = exception
        self.access_count = 0

    @property
    def structuredContent(self):
        self.access_count += 1
        raise self.exception


class SelectiveHostileTrustedEnvelope:
    """Raises on exactly one named envelope property and nowhere else."""

    _ALIASES = frozenset(
        {
            "structured_content",
            "is_error",
            "result",
            "data",
            "structured_content_result",
        }
    )

    def __init__(self, *, target, exception, formatter_result):
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "exception", exception)
        object.__setattr__(self, "formatter_result", formatter_result)
        object.__setattr__(self, "access_count", 0)

    def __getattribute__(self, name):
        target = object.__getattribute__(self, "target")
        if name == target:
            count = object.__getattribute__(self, "access_count")
            object.__setattr__(self, "access_count", count + 1)
            raise object.__getattribute__(self, "exception")
        if name == "structuredContent":
            return {
                "result": object.__getattribute__(self, "formatter_result"),
            }
        if name == "isError":
            return False
        if name == "model_extra":
            return None
        if name in object.__getattribute__(self, "_ALIASES"):
            raise AttributeError(name)
        return object.__getattribute__(self, name)

    def __repr__(self):
        raise RuntimeError("hostile envelope repr detail")

    def __str__(self):
        raise RuntimeError("hostile envelope str detail")


class HostileIdentityValue:
    """A non-string value that refuses coercion, comparison, and rendering."""

    def __init__(self):
        self.access_count = 0

    def _refuse(self):
        self.access_count += 1
        raise RuntimeError("hostile identity detail")

    def __eq__(self, other):
        return self._refuse()

    def __hash__(self):
        return self._refuse()

    def __repr__(self):
        return self._refuse()

    def __str__(self):
        return self._refuse()


class CustomHostileEnvelopeError(Exception):
    """Local ordinary exception used by hostile property probes."""


class NestedHostileEnvelopeError(Exception):
    """Python-3.9-compatible grouped ordinary exception representation."""

    def __init__(self, message, exceptions):
        super().__init__(message)
        self.exceptions = tuple(exceptions)


def _result_container(
    content,
    *,
    container_type="CallToolResult",
    structured_content=_MISSING,
    is_error=False,
):
    envelope_content = (
        {"result": content}
        if structured_content is _MISSING
        else structured_content
    )
    if container_type == "CallToolResult":
        return CallToolResult(
            structured_content=envelope_content,
            is_error=is_error,
        )
    other_type = type(container_type, (), {})
    envelope = other_type()
    envelope.structuredContent = envelope_content
    envelope.isError = is_error
    return envelope


def _legacy_result_overrides(overrides, *, default_content):
    result_container = overrides.pop("result_container", _MISSING)
    if result_container is not _MISSING:
        return result_container
    content = overrides.pop("structured_content_result", default_content)
    container_type = overrides.pop("result_container_type", "CallToolResult")
    return _result_container(content, container_type=container_type)


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
    result_container = _legacy_result_overrides(
        overrides,
        default_content=_content(),
    )
    values = {
        "transport_receipt": _transport(),
        "raw_reference": _raw_reference(),
        "derivative_id": "derivative-001",
        "expected_symbol": "SPY",
        "source_package": FICTIONAL_SOURCE_PACKAGE,
        "source_package_version": FICTIONAL_SOURCE_PACKAGE_VERSION,
        "formatter_shape_id": FICTIONAL_FORMATTER_SHAPE_ID,
        "result_container": result_container,
    }
    values.update(overrides)
    with patch.object(
        admission_module,
        "_MCP_CALL_TOOL_RESULT_TYPE",
        CallToolResult,
    ):
        return admit_formatted_snapshot(**values)


def _webull_content(**overrides):
    # These values are deliberately fictional and were not reconstructed from
    # the destroyed live witness.
    values = {
        "symbol": "SPY",
        "price": "101.25",
        "pre_close": "100.75",
        "change": "0.50",
        "change_ratio": "0.0049",
        "open": "100.80",
        "high": "102.00",
        "low": "100.10",
        "close": "101.25",
        "volume": "123456",
        "bid": "101.20",
        "bid_size": "100",
        "ask": "101.30",
        "ask_size": "200",
        "turnover": "1234567.89",
        "eps": "12.34",
        "eps_ttm": "11.95",
        "lot_size": "1",
        "bps": "45.67",
    }
    values.update(overrides)
    return "\n".join(
        (
            WEBULL_MCP_US_DISCLAIMER_LINE,
            "",
            WEBULL_MCP_HEADER,
            (
                f"  {values['symbol']:>8s}  "
                f"Price: {values['price']:>10s}  "
                f"PreClose: {values['pre_close']:>10s}  "
                f"Change: {values['change']:>8s}  "
                f"Change%: {values['change_ratio']:>8s}"
            ),
            (
                f"{'':>10s}  Open: {values['open']:>10s}  "
                f"High: {values['high']:>10s}  "
                f"Low: {values['low']:>10s}  "
                f"Close: {values['close']:>10s}  "
                f"Vol: {values['volume']:>12s}"
            ),
            (
                f"{'':>10s}  Bid: {values['bid']:>10s} x "
                f"{values['bid_size']:>6s}  Ask: {values['ask']:>10s} x "
                f"{values['ask_size']:>6s}"
            ),
            (
                f"{'':>10s}  Turnover: {values['turnover']:>12s}  "
                f"EPS: {values['eps']:>8s}  "
                f"EPS(TTM): {values['eps_ttm']:>8s}  "
                f"Lot Size: {values['lot_size']:>6s}  "
                f"BPS: {values['bps']:>8s}"
            ),
        )
    )


def _admit_webull(**overrides):
    result_container = _legacy_result_overrides(
        overrides,
        default_content=_webull_content(),
    )
    values = {
        "transport_receipt": _transport(),
        "raw_reference": _raw_reference(),
        "derivative_id": "derivative-webull-001",
        "expected_symbol": "SPY",
        "source_package": WEBULL_MCP_SOURCE_PACKAGE,
        "source_package_version": WEBULL_MCP_SOURCE_PACKAGE_VERSION,
        "formatter_shape_id": WEBULL_MCP_FORMATTER_SHAPE_ID,
        "result_container": result_container,
        "source_file_hashes": dict(WEBULL_MCP_SOURCE_FILE_HASHES),
        "admitted_arguments": {"symbols": "SPY"},
    }
    values.update(overrides)
    with patch.object(
        admission_module,
        "_MCP_CALL_TOOL_RESULT_TYPE",
        CallToolResult,
    ):
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

    def test_privacy_markers_are_never_valid_artifact_identifiers(self):
        markers = (
            "app-key-fictional-sensitive-value",
            "app-secret-fictional-sensitive-value",
            "bearer-token-fictional-sensitive-value",
            "access-token-fictional-sensitive-value",
            "refresh-token-fictional-sensitive-value",
            "authorization-fictional-sensitive-value",
            "signature-fictional-sensitive-value",
            "x-sign-fictional-sensitive-value",
            "account-id-fictional-sensitive-value",
            "account-number-fictional-sensitive-value",
            "request-id-fictional-sensitive-value",
            "trace-identifier-fictional-sensitive-value",
            "session-id-fictional-sensitive-value",
            "profile-path-fictional-sensitive-value",
            "/Users/fictional-sensitive-value",
            "/home/fictional-sensitive-value",
            "~/fictional-sensitive-value",
            r"C:\Users\fictional-sensitive-value",
            "HOME=/fictional-sensitive-value",
            r"USERPROFILE=C:\fictional-sensitive-value",
        ) + _GENERIC_SECRET_IDENTIFIER_MARKERS
        for case_index, marker in enumerate(markers):
            with self.subTest(case_index=case_index):
                self.assertFalse(admission_module._is_safe_identifier(marker))
                self.assertEqual(
                    admission_module._safe_identifier(marker),
                    "UNAVAILABLE",
                )
                self.assertFalse(admission_module._is_safe_symbol(marker))
                transport = _transport(transport_receipt_id=marker)
                raw_reference = _raw_reference(raw_reference_id=marker)
                capture_transport = _transport(capture_session_id=marker)
                capture_reference = _raw_reference(capture_session_id=marker)
                self.assertFalse(transport.valid_for_snapshot_admission())
                self.assertFalse(raw_reference.valid_for_snapshot_admission())
                self.assertFalse(capture_transport.valid_for_snapshot_admission())
                self.assertFalse(capture_reference.valid_for_snapshot_admission())
                with self.assertRaises(ValueError):
                    transport.to_dict()
                with self.assertRaises(ValueError):
                    raw_reference.to_dict()

    def test_fixture_and_parser_identities_are_not_caller_supplied(self):
        raw_parameters = inspect.signature(RawWitnessReference).parameters
        derivative_parameters = inspect.signature(ScrubbedSnapshotDerivative).parameters
        self.assertNotIn("fixture_id", raw_parameters)
        self.assertNotIn("parser_version", derivative_parameters)
        self.assertNotIn("schema_version", derivative_parameters)
        for identity in (
            admission_module.PARSER_VERSION,
            WEBULL_MCP_SOURCE_PACKAGE,
            WEBULL_MCP_SOURCE_PACKAGE_VERSION,
            WEBULL_MCP_FORMATTER_SHAPE_ID,
        ):
            self.assertTrue(admission_module._is_safe_identifier(identity))


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
        outcome = _admit(source_package_version="9.9.9")
        self.assertEqual(outcome.failure_class, "UNSUPPORTED_PACKAGE_VERSION")

    def test_unknown_formatter_shape_fails_closed(self):
        outcome = _admit(formatter_shape_id="unwitnessed.real.shape")
        self.assertEqual(outcome.failure_class, "UNKNOWN_FORMATTER_SHAPE")

    def test_missing_structured_content_fails_closed(self):
        outcome = _admit(
            result_container=CallToolResult(structured_content=None),
        )
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

    def test_hostile_receipt_properties_are_never_evaluated(self):
        hostile_transport = HostileAttributeObject()
        transport_outcome = _admit(transport_receipt=hostile_transport)
        self.assertEqual(
            transport_outcome.failure_class,
            "TRANSPORT_RECEIPT_INVALID",
        )
        self.assertEqual(hostile_transport.access_count, 0)

        hostile_reference = HostileAttributeObject()
        reference_outcome = _admit(raw_reference=hostile_reference)
        self.assertEqual(reference_outcome.failure_class, "RAW_REFERENCE_INVALID")
        self.assertEqual(hostile_reference.access_count, 0)

    def test_hostile_identity_objects_are_not_coerced_compared_or_rendered(self):
        hostile_identity = HostileIdentityValue()
        outcome = admit_formatted_snapshot(
            transport_receipt=object(),
            raw_reference=object(),
            derivative_id="derivative-001",
            expected_symbol="SPY",
            source_package=hostile_identity,
            source_package_version=hostile_identity,
            formatter_shape_id=hostile_identity,
            result_container=object(),
        )
        self.assertEqual(outcome.failure_class, "TRANSPORT_RECEIPT_INVALID")
        self.assertEqual(outcome.source_package, "UNSUPPORTED")
        self.assertEqual(outcome.source_package_version, "UNSUPPORTED")
        self.assertEqual(outcome.formatter_shape_id, "UNSUPPORTED")
        self.assertEqual(hostile_identity.access_count, 0)

        valid_boundary_hostile = HostileIdentityValue()
        valid_boundary_outcome = _admit(source_package=valid_boundary_hostile)
        self.assertEqual(
            valid_boundary_outcome.failure_class,
            "UNSUPPORTED_PACKAGE_VERSION",
        )
        self.assertEqual(valid_boundary_outcome.source_package, "UNSUPPORTED")
        self.assertEqual(valid_boundary_hostile.access_count, 0)

    def test_privacy_identifiers_are_sanitized_from_refusals(self):
        markers = (
            "access-token-fictional-sensitive-value",
        ) + _GENERIC_SECRET_IDENTIFIER_MARKERS
        for case_index, marker in enumerate(markers):
            with self.subTest(case_index=case_index):
                transport_outcome = _admit(
                    transport_receipt=_transport(transport_receipt_id=marker),
                )
                self.assertEqual(
                    transport_outcome.failure_class,
                    "TRANSPORT_RECEIPT_INVALID",
                )
                self.assertEqual(transport_outcome.transport_receipt_id, "UNAVAILABLE")

                raw_outcome = _admit(
                    raw_reference=_raw_reference(raw_reference_id=marker),
                )
                self.assertEqual(raw_outcome.failure_class, "RAW_REFERENCE_INVALID")
                self.assertEqual(raw_outcome.raw_reference_id, "UNAVAILABLE")

                derivative_outcome = _admit(derivative_id=marker)
                self.assertEqual(derivative_outcome.failure_class, "VALUE_TYPE_INVALID")
                revision_outcome = _admit(revision_of=marker)
                self.assertEqual(revision_outcome.failure_class, "VALUE_TYPE_INVALID")

                formatter_outcome = _admit(formatter_shape_id=marker)
                self.assertEqual(
                    formatter_outcome.failure_class,
                    "UNKNOWN_FORMATTER_SHAPE",
                )
                self.assertEqual(formatter_outcome.formatter_shape_id, "UNSUPPORTED")

                version_outcome = _admit(source_package_version=marker)
                self.assertEqual(
                    version_outcome.failure_class,
                    "UNSUPPORTED_PACKAGE_VERSION",
                )
                self.assertEqual(version_outcome.source_package_version, "UNSUPPORTED")

                package_outcome = _admit(source_package=marker)
                self.assertEqual(
                    package_outcome.failure_class,
                    "UNSUPPORTED_PACKAGE_VERSION",
                )
                self.assertEqual(package_outcome.source_package, "UNSUPPORTED")

        symbol_marker = "account-id-fictional-sensitive-value"
        symbol_outcome = _admit(
            expected_symbol=symbol_marker,
            structured_content_result=_content(symbol=symbol_marker),
        )
        self.assertEqual(symbol_outcome.failure_class, "IDENTITY_PATTERN_PRESENT")

    def test_direct_refusal_rejects_privacy_bearing_identifier_fields(self):
        markers = (
            "request-id-fictional-sensitive-value",
        ) + _GENERIC_SECRET_IDENTIFIER_MARKERS
        for case_index, marker in enumerate(markers):
            for field_name in ("raw_reference_id", "transport_receipt_id"):
                values = {
                    "failure_class": "PARSER_INTERNAL_ERROR",
                    "source_package": "UNSUPPORTED",
                    "source_package_version": "UNSUPPORTED",
                    "formatter_shape_id": "UNSUPPORTED",
                    "raw_reference_id": "raw-reference-001",
                    "transport_receipt_id": "transport-001",
                }
                values[field_name] = marker
                with self.subTest(
                    case_index=case_index,
                    field_name=field_name,
                ), self.assertRaises(ValueError):
                    AdmissionRefusal(**values)

    def test_generic_secret_scanner_remains_label_aware(self):
        safe_texts = (
            "token count",
            "secret market status",
            "credential policy",
            "passwordless",
            "market_token",
            "secretary: value",
        )
        for case_index, safe_text in enumerate(safe_texts):
            with self.subTest(case_index=case_index):
                self.assertIsNone(admission_module._SECRET_PATTERN.search(safe_text))

    def test_private_refusal_never_evaluates_hostile_identifier_values(self):
        hostile = HostileIdentityValue()
        outcome = admission_module._refusal(
            "PARSER_INTERNAL_ERROR",
            source_package=hostile,
            source_package_version=hostile,
            formatter_shape_id=hostile,
            raw_reference_id=hostile,
            transport_receipt_id=hostile,
        )
        self.assertEqual(outcome.raw_reference_id, "UNAVAILABLE")
        self.assertEqual(outcome.transport_receipt_id, "UNAVAILABLE")
        self.assertEqual(outcome.source_package, "UNSUPPORTED")
        self.assertEqual(outcome.source_package_version, "UNSUPPORTED")
        self.assertEqual(outcome.formatter_shape_id, "UNSUPPORTED")
        self.assertEqual(hostile.access_count, 0)


class TestWebullMCP116FormatterContract(TestCase):
    def test_admission_api_requires_original_envelope(self):
        parameters = inspect.signature(admit_formatted_snapshot).parameters
        self.assertIn("result_container", parameters)
        self.assertNotIn("result_container_type", parameters)
        self.assertNotIn("structured_content_result", parameters)

    def test_original_mcp_type_import_failure_is_value_free(self):
        with patch.object(
            admission_module,
            "_MCP_CALL_TOOL_RESULT_TYPE",
            None,
        ), patch(
            "builtins.__import__",
            side_effect=ImportError("fictional-sensitive-import-detail"),
        ):
            outcome = admit_formatted_snapshot(
                transport_receipt=_transport(),
                raw_reference=_raw_reference(),
                derivative_id="derivative-webull-001",
                expected_symbol="SPY",
                source_package=WEBULL_MCP_SOURCE_PACKAGE,
                source_package_version=WEBULL_MCP_SOURCE_PACKAGE_VERSION,
                formatter_shape_id=WEBULL_MCP_FORMATTER_SHAPE_ID,
                result_container=CallToolResult(
                    structured_content={"result": _webull_content()},
                ),
                source_file_hashes=dict(WEBULL_MCP_SOURCE_FILE_HASHES),
                admitted_arguments={"symbols": "SPY"},
            )
        self.assertEqual(outcome.failure_class, "RESULT_CONTAINER_MISSING")
        self.assertNotIn(
            "fictional-sensitive-import-detail",
            json.dumps(outcome.to_dict()),
        )
        self.assertFalse(outcome.execution_authority)

    def test_hostile_trusted_envelope_property_is_evaluated_once_and_controlled(self):
        envelope = HostileTrustedEnvelope(RuntimeError("hostile envelope detail"))
        with patch.object(
            admission_module,
            "_MCP_CALL_TOOL_RESULT_TYPE",
            HostileTrustedEnvelope,
        ):
            outcome = admit_formatted_snapshot(
                transport_receipt=_transport(),
                raw_reference=_raw_reference(),
                derivative_id="derivative-webull-001",
                expected_symbol="SPY",
                source_package=WEBULL_MCP_SOURCE_PACKAGE,
                source_package_version=WEBULL_MCP_SOURCE_PACKAGE_VERSION,
                formatter_shape_id=WEBULL_MCP_FORMATTER_SHAPE_ID,
                result_container=envelope,
                source_file_hashes=dict(WEBULL_MCP_SOURCE_FILE_HASHES),
                admitted_arguments={"symbols": "SPY"},
            )
        self.assertEqual(outcome.failure_class, "RESULT_CONTAINER_MISSING")
        self.assertEqual(envelope.access_count, 1)
        self.assertNotIn("hostile", json.dumps(outcome.to_dict()))

    def test_every_named_envelope_property_has_one_controlled_access(self):
        property_names = (
            "structuredContent",
            "isError",
            "structured_content",
            "is_error",
            "result",
            "data",
            "structured_content_result",
            "model_extra",
        )
        for case_index, property_name in enumerate(property_names):
            with self.subTest(case_index=case_index):
                envelope = SelectiveHostileTrustedEnvelope(
                    target=property_name,
                    exception=RuntimeError("hostile envelope detail"),
                    formatter_result=_webull_content(),
                )
                with patch.object(
                    admission_module,
                    "_MCP_CALL_TOOL_RESULT_TYPE",
                    SelectiveHostileTrustedEnvelope,
                ):
                    outcome = admit_formatted_snapshot(
                        transport_receipt=_transport(),
                        raw_reference=_raw_reference(),
                        derivative_id="derivative-webull-001",
                        expected_symbol="SPY",
                        source_package=WEBULL_MCP_SOURCE_PACKAGE,
                        source_package_version=WEBULL_MCP_SOURCE_PACKAGE_VERSION,
                        formatter_shape_id=WEBULL_MCP_FORMATTER_SHAPE_ID,
                        result_container=envelope,
                        source_file_hashes=dict(WEBULL_MCP_SOURCE_FILE_HASHES),
                        admitted_arguments={"symbols": "SPY"},
                    )
                self.assertEqual(outcome.failure_class, "RESULT_CONTAINER_MISSING")
                self.assertEqual(envelope.access_count, 1)
                self.assertNotIn("hostile", json.dumps(outcome.to_dict()))

    def test_hostile_content_and_meta_access_are_controlled_and_value_free(self):
        exception_factories = (
            lambda: RuntimeError("hostile non-authoritative detail"),
            lambda: ValueError("hostile non-authoritative detail"),
            lambda: TypeError("hostile non-authoritative detail"),
            lambda: CustomHostileEnvelopeError(
                "hostile non-authoritative detail"
            ),
            lambda: NestedHostileEnvelopeError(
                "hostile non-authoritative detail",
                [RuntimeError("nested hostile detail")],
            ),
        )
        for property_index, property_name in enumerate(("content", "_meta")):
            for exception_index, exception_factory in enumerate(exception_factories):
                with self.subTest(
                    property_index=property_index,
                    exception_index=exception_index,
                ):
                    envelope = SelectiveHostileTrustedEnvelope(
                        target=property_name,
                        exception=exception_factory(),
                        formatter_result=_webull_content(),
                    )
                    with patch.object(
                        admission_module,
                        "_MCP_CALL_TOOL_RESULT_TYPE",
                        SelectiveHostileTrustedEnvelope,
                    ):
                        outcome = admit_formatted_snapshot(
                            transport_receipt=_transport(),
                            raw_reference=_raw_reference(),
                            derivative_id="derivative-webull-001",
                            expected_symbol="SPY",
                            source_package=WEBULL_MCP_SOURCE_PACKAGE,
                            source_package_version=WEBULL_MCP_SOURCE_PACKAGE_VERSION,
                            formatter_shape_id=WEBULL_MCP_FORMATTER_SHAPE_ID,
                            result_container=envelope,
                            source_file_hashes=dict(WEBULL_MCP_SOURCE_FILE_HASHES),
                            admitted_arguments={"symbols": "SPY"},
                        )
                    encoded = json.dumps(outcome.to_dict())
                    self.assertEqual(
                        outcome.failure_class,
                        "RESULT_CONTAINER_MISSING",
                    )
                    self.assertEqual(envelope.access_count, 1)
                    self.assertNotIn("hostile", encoded)
                    self.assertNotIn("content", encoded)
                    self.assertNotIn("_meta", encoded)
                    self.assertFalse(outcome.execution_authority)

    def test_control_flow_exceptions_propagate_from_envelope_access(self):
        exception_types = (
            KeyboardInterrupt,
            SystemExit,
            asyncio.CancelledError,
        )
        for case_index, exception_type in enumerate(exception_types):
            with self.subTest(case_index=case_index):
                envelope = HostileTrustedEnvelope(exception_type())
                with patch.object(
                    admission_module,
                    "_MCP_CALL_TOOL_RESULT_TYPE",
                    HostileTrustedEnvelope,
                ), self.assertRaises(exception_type):
                    admit_formatted_snapshot(
                        transport_receipt=_transport(),
                        raw_reference=_raw_reference(),
                        derivative_id="derivative-webull-001",
                        expected_symbol="SPY",
                        source_package=WEBULL_MCP_SOURCE_PACKAGE,
                        source_package_version=WEBULL_MCP_SOURCE_PACKAGE_VERSION,
                        formatter_shape_id=WEBULL_MCP_FORMATTER_SHAPE_ID,
                        result_container=envelope,
                        source_file_hashes=dict(WEBULL_MCP_SOURCE_FILE_HASHES),
                        admitted_arguments={"symbols": "SPY"},
                    )
                self.assertEqual(envelope.access_count, 1)

    def test_original_envelope_path_is_exact(self):
        missing_attribute = CallToolResult(
            structured_content=_MISSING,
            is_error=False,
        )
        self.assertEqual(
            _admit_webull(result_container=missing_attribute).failure_class,
            "STRUCTURED_CONTENT_MISSING",
        )

        cases = (
            (CallToolResult(structured_content=None), "STRUCTURED_CONTENT_MISSING"),
            (CallToolResult(structured_content=[]), "VALUE_TYPE_INVALID"),
            (CallToolResult(structured_content={}), "RESULT_CONTAINER_MISSING"),
            (
                CallToolResult(structured_content={"result": ["not-text"]}),
                "VALUE_TYPE_INVALID",
            ),
            (
                CallToolResult(
                    structured_content={"result": _webull_content(), "data": "alias"}
                ),
                "AMBIGUOUS_FIELD",
            ),
            (
                CallToolResult(
                    structured_content={"result": _webull_content()},
                    is_error=True,
                ),
                "RESULT_CONTAINER_MISSING",
            ),
            (
                CallToolResult(
                    structured_content={"result": _webull_content()},
                    is_error=None,
                ),
                "VALUE_TYPE_INVALID",
            ),
        )
        for envelope, failure_class in cases:
            with self.subTest(failure_class=failure_class):
                outcome = _admit_webull(result_container=envelope)
                self.assertEqual(outcome.failure_class, failure_class)
                self.assertFalse(outcome.execution_authority)

        lookalike_type = type("CallToolResult", (), {})
        lookalike_type.__module__ = "mcp.types"
        lookalike = lookalike_type()
        lookalike.structuredContent = {"result": _webull_content()}
        lookalike.isError = False
        self.assertEqual(
            _admit_webull(result_container=lookalike).failure_class,
            "RESULT_CONTAINER_MISSING",
        )

    def test_envelope_aliases_are_refused(self):
        structured_alias = CallToolResult(
            structured_content={"result": _webull_content()},
        )
        structured_alias.structured_content = {"result": _webull_content()}
        self.assertEqual(
            _admit_webull(result_container=structured_alias).failure_class,
            "AMBIGUOUS_FIELD",
        )

        error_alias = CallToolResult(
            structured_content={"result": _webull_content()},
        )
        error_alias.is_error = False
        self.assertEqual(
            _admit_webull(result_container=error_alias).failure_class,
            "AMBIGUOUS_FIELD",
        )

        for alias_name in ("result", "data", "structured_content_result"):
            with self.subTest(alias_name=alias_name):
                top_level_alias = CallToolResult(
                    structured_content={"result": _webull_content()},
                )
                setattr(top_level_alias, alias_name, _webull_content())
                self.assertEqual(
                    _admit_webull(result_container=top_level_alias).failure_class,
                    "AMBIGUOUS_FIELD",
                )

        extra_container = CallToolResult(
            structured_content={"result": _webull_content()},
        )
        extra_container.model_extra = {"alternate": _webull_content()}
        self.assertEqual(
            _admit_webull(result_container=extra_container).failure_class,
            "AMBIGUOUS_FIELD",
        )

    def test_external_text_and_meta_cannot_substitute_for_structured_result(self):
        no_structured_result = CallToolResult(
            structured_content={},
            content=[_webull_content()],
            meta={"result": _webull_content()},
        )
        outcome = _admit_webull(result_container=no_structured_result)
        self.assertEqual(outcome.failure_class, "RESULT_CONTAINER_MISSING")

        authoritative_structured_result = CallToolResult(
            structured_content={"result": _webull_content()},
            content=["non-authoritative text"],
            meta={"result": "non-authoritative metadata"},
        )
        admitted = _admit_webull(result_container=authoritative_structured_result)
        self.assertIsInstance(admitted, ScrubbedSnapshotDerivative)

    def test_absent_error_flag_is_permitted_but_fastmcp_wrapper_is_not(self):
        no_error_attribute = CallToolResult(
            structured_content={"result": _webull_content()},
            is_error=_MISSING,
        )
        self.assertIsInstance(
            _admit_webull(result_container=no_error_attribute),
            ScrubbedSnapshotDerivative,
        )

        fastmcp_alias_type = type("CallToolResult", (), {})
        fastmcp_alias_type.__module__ = "mcp.types"
        fastmcp_alias = fastmcp_alias_type()
        fastmcp_alias.structured_content = {"result": _webull_content()}
        fastmcp_alias.is_error = False
        self.assertEqual(
            _admit_webull(result_container=fastmcp_alias).failure_class,
            "RESULT_CONTAINER_MISSING",
        )

    def test_exact_fictional_seven_line_shape_creates_pending_candidate(self):
        outcome = _admit_webull()
        self.assertIsInstance(outcome, ScrubbedSnapshotDerivative)
        self.assertEqual(outcome.source_package_version, "1.1.6")
        self.assertEqual(outcome.formatter_shape_id, WEBULL_MCP_FORMATTER_SHAPE_ID)
        self.assertEqual(outcome.instrument_symbol, "SPY")
        self.assertEqual(
            dict(outcome.market_fields),
            {
                "last_price": "101.25",
                "bid": "101.20",
                "ask": "101.30",
                "spread": "0.10",
                "volume": "123456",
            },
        )
        self.assertIsNone(outcome.observed_at)
        self.assertEqual(outcome.observed_at_source, "UNAVAILABLE")
        self.assertEqual(outcome.human_review_status, "PENDING")
        self.assertFalse(outcome.fixture_admitted)
        self.assertFalse(outcome.execution_authority)

    def test_source_hash_identity_is_exact_and_fail_closed(self):
        missing = _admit_webull(source_file_hashes=None)
        self.assertEqual(missing.failure_class, "SOURCE_HASH_MISMATCH")

        changed = dict(WEBULL_MCP_SOURCE_FILE_HASHES)
        changed["formatters.py"] = "0" * 64
        mismatch = _admit_webull(source_file_hashes=changed)
        self.assertEqual(mismatch.failure_class, "SOURCE_HASH_MISMATCH")

        extra = dict(WEBULL_MCP_SOURCE_FILE_HASHES)
        extra["unreviewed.py"] = "0" * 64
        broader = _admit_webull(source_file_hashes=extra)
        self.assertEqual(broader.failure_class, "SOURCE_HASH_MISMATCH")

    def test_invocation_contract_requires_exact_symbols_string(self):
        for arguments in (
            None,
            {"symbols": ["SPY"]},
            {"symbol": "SPY"},
            {"symbols": "SPY", "category": "US_STOCK"},
            {"symbols": "QQQ"},
        ):
            with self.subTest(arguments=arguments):
                outcome = _admit_webull(admitted_arguments=arguments)
                self.assertEqual(outcome.failure_class, "FIELD_LAYOUT_MISMATCH")

    def test_custody_inputs_are_not_mutated_or_retained(self):
        hashes = dict(WEBULL_MCP_SOURCE_FILE_HASHES)
        arguments = {"symbols": "SPY"}
        original_hashes = dict(hashes)
        original_arguments = dict(arguments)
        outcome = _admit_webull(
            source_file_hashes=hashes,
            admitted_arguments=arguments,
        )
        self.assertIsInstance(outcome, ScrubbedSnapshotDerivative)
        self.assertEqual(hashes, original_hashes)
        self.assertEqual(arguments, original_arguments)
        encoded = json.dumps(outcome.to_dict())
        self.assertNotIn("b58d4bda", encoded)
        self.assertNotIn('"symbols"', encoded)
        self.assertNotIn(WEBULL_MCP_US_DISCLAIMER_LINE, encoded)

    def test_package_version_shape_and_result_container_are_exact(self):
        unsupported_version = _admit_webull(source_package_version="1.1.7")
        self.assertEqual(
            unsupported_version.failure_class,
            "UNSUPPORTED_PACKAGE_VERSION",
        )
        unsupported_shape = _admit_webull(formatter_shape_id="other.shape")
        self.assertEqual(unsupported_shape.failure_class, "UNKNOWN_FORMATTER_SHAPE")
        wrong_container = _admit_webull(result_container_type="dict")
        self.assertEqual(wrong_container.failure_class, "RESULT_CONTAINER_MISSING")

    def test_disclaimer_header_and_separator_are_exact(self):
        changed_disclaimer = _webull_content().replace(
            WEBULL_MCP_US_DISCLAIMER_LINE,
            "Different disclaimer",
            1,
        )
        self.assertEqual(
            _admit_webull(
                structured_content_result=changed_disclaimer
            ).failure_class,
            "DISCLAIMER_MISMATCH",
        )

        changed_separator = _webull_content().replace("\n\n", "\nnot-empty\n", 1)
        self.assertEqual(
            _admit_webull(
                structured_content_result=changed_separator
            ).failure_class,
            "DISCLAIMER_MISMATCH",
        )

        changed_header = _webull_content().replace(
            WEBULL_MCP_HEADER,
            "=== Other Snapshot ===",
            1,
        )
        self.assertEqual(
            _admit_webull(structured_content_result=changed_header).failure_class,
            "FIELD_LAYOUT_MISMATCH",
        )

    def test_line_count_and_order_fail_closed(self):
        lines = _webull_content().split("\n")
        base_only = "\n".join(lines[:-1])
        self.assertEqual(
            _admit_webull(structured_content_result=base_only).failure_class,
            "LINE_COUNT_MISMATCH",
        )

        reordered = list(lines)
        reordered[4], reordered[5] = reordered[5], reordered[4]
        self.assertEqual(
            _admit_webull(structured_content_result="\n".join(reordered)).failure_class,
            "FIELD_LAYOUT_MISMATCH",
        )

        trailing = _webull_content() + "\n"
        self.assertEqual(
            _admit_webull(structured_content_result=trailing).failure_class,
            "LINE_COUNT_MISMATCH",
        )

    def test_extended_and_overnight_sections_are_not_admitted(self):
        lines = _webull_content().split("\n")
        extended = list(lines)
        extended[-1] = (
            f"{'':>10s}  ExtHr Price: {'101.40':>10s}  High: {'102.00':>10s}  "
            f"Low: {'100.00':>10s}  Change: {'0.15':>8s} ({'0.0015'})  "
            f"Vol: {'500':>12s}"
        )
        self.assertEqual(
            _admit_webull(structured_content_result="\n".join(extended)).failure_class,
            "OPTIONAL_SECTION_UNSUPPORTED",
        )

        overnight = _webull_content() + (
            "\n" + f"{'':>10s}  OVN Price: {'101.10':>10s}"
        )
        self.assertEqual(
            _admit_webull(structured_content_result=overnight).failure_class,
            "OPTIONAL_SECTION_UNSUPPORTED",
        )

    def test_multiple_symbol_blocks_are_refused(self):
        lines = _webull_content().split("\n")
        second_block = lines[3:6]
        multi = "\n".join((*lines[:-1], *second_block, lines[-1]))
        outcome = _admit_webull(structured_content_result=multi)
        self.assertEqual(outcome.failure_class, "MULTI_SYMBOL_RESPONSE")

    def test_symbol_match_is_exact(self):
        outcome = _admit_webull(structured_content_result=_webull_content(symbol="QQQ"))
        self.assertEqual(outcome.failure_class, "SYMBOL_MISMATCH")

    def test_required_market_values_cannot_be_missing(self):
        for field in ("price", "bid", "ask", "volume"):
            with self.subTest(field=field):
                outcome = _admit_webull(
                    structured_content_result=_webull_content(**{field: "N/A"})
                )
                self.assertEqual(outcome.failure_class, "REQUIRED_FIELD_MISSING")

    def test_all_formatter_numeric_fields_are_validated(self):
        cases = (
            {"price": "NaN"},
            {"bid": "-1"},
            {"bid": "102", "ask": "101"},
            {"volume": "1.5"},
            {"pre_close": "not-a-number"},
            {"bid_size": "1.5"},
            {"turnover": "Infinity"},
            {"lot_size": "1.5"},
        )
        for values in cases:
            with self.subTest(values=values):
                outcome = _admit_webull(
                    structured_content_result=_webull_content(**values)
                )
                self.assertEqual(outcome.failure_class, "VALUE_TYPE_INVALID")

    def test_nonadmitted_na_values_remain_categorical(self):
        outcome = _admit_webull(
            structured_content_result=_webull_content(
                pre_close="N/A",
                change="N/A",
                bid_size="N/A",
                eps="N/A",
            )
        )
        self.assertIsInstance(outcome, ScrubbedSnapshotDerivative)
        self.assertEqual(
            outcome.null_field_names,
            ("bid_size", "change", "eps", "pre_close"),
        )
        self.assertNotIn("pre_close", outcome.market_fields)
        self.assertIn(
            "pre_close",
            outcome.recognized_but_not_admitted_field_names,
        )

    def test_empty_fundamentals_candidate_is_impossible_for_this_shape(self):
        outcome = _admit_webull(
            structured_content_result=_webull_content(
                turnover="N/A",
                eps="N/A",
                eps_ttm="N/A",
                lot_size="N/A",
                bps="N/A",
            )
        )
        self.assertEqual(outcome.failure_class, "FIELD_LAYOUT_MISMATCH")

    def test_secret_scan_covers_every_sealed_marker_class(self):
        markers = (
            "app_key=fictional-sensitive-value",
            "webull_app_key_id=fictional-sensitive-value",
            "app key: fictional-sensitive-value",
            "app-secret=fictional-sensitive-value",
            "app secret: fictional-sensitive-value",
            "Bearer fictional-sensitive-value",
            "Bearer: fictional-sensitive-value",
            "bearer_token=fictional-sensitive-value",
            "access_token=fictional-sensitive-value",
            "access token: fictional-sensitive-value",
            "refresh-token=fictional-sensitive-value",
            "refresh token: fictional-sensitive-value",
            "authorization=fictional-sensitive-value",
            "signature=fictional-sensitive-value",
            "x-sign=fictional-sensitive-value",
        ) + _GENERIC_SECRET_CONTENT_MARKERS
        for case_index, marker in enumerate(markers):
            with self.subTest(case_index=case_index):
                outcome = _admit_webull(
                    structured_content_result=_webull_content(eps=marker)
                )
                encoded = json.dumps(outcome.to_dict())
                self.assertEqual(outcome.failure_class, "SECRET_PATTERN_PRESENT")
                self.assertNotIn("fictional-sensitive-value", encoded)
                self.assertFalse(outcome.execution_authority)

    def test_identity_scan_covers_every_sealed_marker_class(self):
        markers = (
            "account_id=fictional-sensitive-value",
            "account-number=fictional-sensitive-value",
            "account id: fictional-sensitive-value",
            "request_id=fictional-sensitive-value",
            "request id: fictional-sensitive-value",
            "trace-identifier=fictional-sensitive-value",
            "trace identifier: fictional-sensitive-value",
            "session_id=fictional-sensitive-value",
            "session-identifier=fictional-sensitive-value",
            "session id: fictional-sensitive-value",
            "profile_path=/fictional-sensitive-value",
            "profile path: /fictional-sensitive-value",
            "/profiles/fictional-sensitive-value",
            "/Users/fictional-sensitive-value",
            "/home/fictional-sensitive-value",
            "~/fictional-sensitive-value",
            r"C:\Users\fictional-sensitive-value",
            "HOME=/fictional-sensitive-value",
            r"USERPROFILE=C:\fictional-sensitive-value",
        )
        for case_index, marker in enumerate(markers):
            with self.subTest(case_index=case_index):
                outcome = _admit_webull(
                    structured_content_result=_webull_content(eps=marker)
                )
                encoded = json.dumps(outcome.to_dict())
                self.assertEqual(outcome.failure_class, "IDENTITY_PATTERN_PRESENT")
                self.assertNotIn("fictional-sensitive-value", encoded)
                self.assertFalse(outcome.execution_authority)

    def test_secret_scan_precedes_source_identity_validation(self):
        outcome = _admit_webull(
            source_file_hashes={"formatters.py": "0" * 64},
            structured_content_result="access_token=fictional-sensitive-value",
        )
        self.assertEqual(outcome.failure_class, "SECRET_PATTERN_PRESENT")
        self.assertNotIn("fictional-sensitive-value", json.dumps(outcome.to_dict()))

    def test_real_derivative_is_value_free_outside_admitted_fields(self):
        outcome = _admit_webull()
        self.assertIsInstance(outcome, ScrubbedSnapshotDerivative)
        encoded = json.dumps(outcome.to_dict())
        self.assertNotIn("PreClose:", encoded)
        self.assertNotIn("Turnover:", encoded)
        self.assertNotIn("1234567.89", encoded)
        self.assertNotIn("raw_content", encoded)
        self.assertFalse(outcome.execution_authority)

    def test_real_candidate_can_be_human_registered_without_fixture_authority(self):
        candidate = _admit_webull()
        approved = register_human_approved_derivative(
            candidate,
            human_review_authorized=True,
        )
        self.assertIsInstance(approved, ScrubbedSnapshotDerivative)
        self.assertEqual(approved.human_review_status, "APPROVED")
        self.assertEqual(len(approved.sha256_registration), 64)
        self.assertFalse(approved.fixture_admitted)
        self.assertFalse(approved.execution_authority)

    def test_invalid_transport_stops_before_formatter_admission(self):
        outcome = _admit_webull(
            transport_receipt=_transport(broker_requests_executed=0),
            structured_content_result="access_token=must-not-be-parsed",
        )
        self.assertEqual(outcome.failure_class, "TRANSPORT_RECEIPT_INVALID")


class TestHumanReviewAndHashing(TestCase):
    def test_hash_registration_requires_explicit_human_authorization(self):
        candidate = _admit()
        outcome = register_human_approved_derivative(
            candidate,
            human_review_authorized=False,
        )
        self.assertEqual(outcome.failure_class, "HUMAN_REVIEW_REQUIRED")

    def test_hostile_non_derivative_is_refused_without_property_access(self):
        hostile = HostileAttributeObject()
        outcome = register_human_approved_derivative(
            hostile,
            human_review_authorized=False,
        )
        self.assertEqual(outcome.failure_class, "HUMAN_REVIEW_REQUIRED")
        self.assertEqual(outcome.raw_reference_id, "UNAVAILABLE")
        self.assertEqual(outcome.transport_receipt_id, "UNAVAILABLE")
        self.assertEqual(hostile.access_count, 0)

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
