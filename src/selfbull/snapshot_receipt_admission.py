"""Fail-closed snapshot receipt admission for SELFBULL-004B.

This module is deliberately offline. It does not start MCP, authenticate,
read token state, invoke a broker, write fixtures, or append to a ledger.
Only explicitly versioned formatter contracts are registered.  The Webull
MCP 1.1.6 contract accepts source identity and formatter text supplied by a
separately governed capture boundary; this module never performs that capture.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import InitVar, dataclass, field, replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple, Union

TRANSPORT_SCHEMA_VERSION = "004B.snapshot-transport-receipt.v1"
DERIVATIVE_SCHEMA_VERSION = "004B.snapshot-derivative.v1"
PARSER_VERSION = "004B.snapshot-parser.v1"

FICTIONAL_SOURCE_PACKAGE = "webull-openapi-mcp"
FICTIONAL_SOURCE_PACKAGE_VERSION = "0.0.0-fictional-test"
FICTIONAL_FORMATTER_SHAPE_ID = "fictional.stock_snapshot.kv.v1"
FICTIONAL_RESULT_CONTAINER_TYPE = "CallToolResult"
FICTIONAL_HEADER = "FORMAT=FICTIONAL_STOCK_SNAPSHOT_V1"

WEBULL_MCP_SOURCE_PACKAGE = "webull-openapi-mcp"
WEBULL_MCP_SOURCE_PACKAGE_VERSION = "1.1.6"
WEBULL_MCP_FORMATTER_SHAPE_ID = (
    "004B.womcp-1.1.6.stock-snapshot.us-default."
    "single-symbol.fundamentals.v1"
)
WEBULL_MCP_RESULT_CONTAINER_TYPE = "CallToolResult"
_MCP_CALL_TOOL_RESULT_TYPE: Optional[type] = None
WEBULL_MCP_SOURCE_FILE_HASHES = MappingProxyType(
    {
        "tools/market_data/stock.py": (
            "b58d4bda3169f93a4d87ddb021c14e29e1fab8cf1d3df738a93e7c0de68fbab5"
        ),
        "formatters.py": (
            "f0cd28003934a07cef23e1b07f70864563b6823469cb0f404974ba748f59555d"
        ),
    }
)
WEBULL_MCP_US_DISCLAIMER_LINE = (
    "⚠️ Disclaimer: The information provided by this tool is for reference "
    "only and does not constitute investment advice. Trading involves risk; "
    "please make decisions carefully."
)
WEBULL_MCP_HEADER = "=== Stock Snapshot ==="

FAILURE_CLASSES = frozenset(
    {
        "UNKNOWN_FORMATTER_SHAPE",
        "UNSUPPORTED_PACKAGE_VERSION",
        "STRUCTURED_CONTENT_MISSING",
        "RESULT_CONTAINER_MISSING",
        "REQUIRED_FIELD_MISSING",
        "AMBIGUOUS_FIELD",
        "VALUE_TYPE_INVALID",
        "SYMBOL_MISMATCH",
        "TIMESTAMP_UNAVAILABLE",
        "SECRET_PATTERN_PRESENT",
        "IDENTITY_PATTERN_PRESENT",
        "PARSER_INTERNAL_ERROR",
        "TRANSPORT_RECEIPT_INVALID",
        "RAW_REFERENCE_INVALID",
        "HUMAN_REVIEW_REQUIRED",
        "SOURCE_HASH_MISMATCH",
        "DISCLAIMER_MISMATCH",
        "LINE_COUNT_MISMATCH",
        "FIELD_LAYOUT_MISMATCH",
        "MULTI_SYMBOL_RESPONSE",
        "OPTIONAL_SECTION_UNSUPPORTED",
    }
)

_EXPECTED_TOOL = "get_stock_snapshot"
_EXPECTED_VISIBLE_TOOLS = (_EXPECTED_TOOL,)
_EXPECTED_CANONICAL_FIELDS = ("symbol",)
_EXPECTED_ADMITTED_ARGUMENT_FIELDS = ("symbols",)
_EXPECTED_KEYS = (
    "symbol",
    "last_price",
    "bid",
    "ask",
    "volume",
    "observed_at",
    "market_status",
    "delayed",
)
_EXPECTED_MARKET_FIELDS = frozenset(
    {"last_price", "bid", "ask", "spread", "volume", "market_status", "delayed"}
)
_EXPECTED_DERIVATIVE_ADMITTED_FIELDS = tuple(sorted((*_EXPECTED_KEYS, "spread")))
_WEBULL_BROKER_FIELD_NAMES = (
    "symbol",
    "price",
    "pre_close",
    "change",
    "change_ratio",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "bid",
    "bid_size",
    "ask",
    "ask_size",
    "turnover",
    "eps",
    "eps_ttm",
    "lot_size",
    "bps",
)
_WEBULL_ADMITTED_FIELD_NAMES = tuple(
    sorted(("symbol", "last_price", "bid", "ask", "volume", "spread"))
)
_WEBULL_RECOGNIZED_NOT_ADMITTED_FIELD_NAMES = (
    "pre_close",
    "change",
    "change_ratio",
    "open",
    "high",
    "low",
    "close",
    "bid_size",
    "ask_size",
    "turnover",
    "eps",
    "eps_ttm",
    "lot_size",
    "bps",
)
_WEBULL_MARKET_FIELDS = frozenset(
    {"last_price", "bid", "ask", "spread", "volume"}
)
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SAFE_SYMBOL = re.compile(r"^[A-Za-z0-9.^:/_-]{1,32}$")
_DERIVATIVE_CONSTRUCTION_SEAL = object()
_FORBIDDEN_VOCABULARY = re.compile(
    r"(?i)\b(account|balance|position|order|watchlist|trade|recommendation|prediction)\b"
)
_SECRET_PATTERN = re.compile(
    r"(?i)("
    r"\b(?:webull[\s_-]*)?app[\s_-]*key(?:[\s_-]*id)?\b|"
    r"\b(?:webull[\s_-]*)?app[\s_-]*secret\b|"
    r"\bbearer(?:[\s_-]*token\b|\s+|\s*[:=])|"
    r"\baccess[\s_-]*token\b|"
    r"\brefresh[\s_-]*token\b|"
    r"\bauthorization\b|"
    r"\bsignature\b|"
    r"\bx-sign\b"
    r")"
)
_IDENTITY_PATTERN = re.compile(
    r"(?i)("
    r"\baccount[\s_-]*(?:id|identifier|number)\b|"
    r"\brequest[\s_-]*(?:id|identifier)\b|"
    r"\btrace[\s_-]*(?:id|identifier)\b|"
    r"\bsession[\s_-]*(?:id|identifier)\b|"
    r"\bprofile[\s_-]*(?:path|dir|directory)\b|"
    r"\b(?:home|userprofile)(?:[\s_-]*(?:path|dir|directory))?\s*[:=]\s*"
    r"(?:~[/\\]|/|\\|[A-Za-z]:[/\\])|"
    r"(?:^|[\s=:'\"])(?:~[/\\]|/(?:users|home)/|\\users\\|/profiles?/|\\profiles\\)"
    r")"
)

_WEBULL_PRIMARY_LINE = re.compile(
    r"^  (?P<symbol>.+?)  Price: (?P<price>.+?)  "
    r"PreClose: (?P<pre_close>.+?)  Change: (?P<change>.+?)  "
    r"Change%: (?P<change_ratio>.+)$"
)
_WEBULL_OHLCV_LINE = re.compile(
    r"^ {12}Open: (?P<open>.+?)  High: (?P<high>.+?)  "
    r"Low: (?P<low>.+?)  Close: (?P<close>.+?)  Vol: (?P<volume>.+)$"
)
_WEBULL_QUOTE_LINE = re.compile(
    r"^ {12}Bid: (?P<bid>.+?) x (?P<bid_size>.+?)  "
    r"Ask: (?P<ask>.+?) x (?P<ask_size>.+)$"
)
_WEBULL_FUNDAMENTALS_LINE = re.compile(
    r"^ {12}Turnover: (?P<turnover>.+?)  EPS: (?P<eps>.+?)  "
    r"EPS\(TTM\): (?P<eps_ttm>.+?)  Lot Size: (?P<lot_size>.+?)  "
    r"BPS: (?P<bps>.+)$"
)


def _freeze_mapping(value: Mapping[str, Optional[str]]) -> Mapping[str, Optional[str]]:
    return MappingProxyType(dict(value))


def _is_safe_identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(_SAFE_IDENTIFIER.fullmatch(value))


def _safe_identifier(value: Any) -> str:
    return value if _is_safe_identifier(value) else "UNAVAILABLE"


def _aware_iso8601(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _is_aware_iso8601(value: Any) -> bool:
    return _aware_iso8601(value) is not None


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TransportReceipt:
    transport_receipt_id: str
    capture_session_id: str
    transport_plane: str
    tool_name: str
    visible_tool_names: Tuple[str, ...]
    canonical_argument_field_names: Tuple[str, ...]
    admitted_argument_field_names: Tuple[str, ...]
    optional_arguments_forwarded: bool
    broker_request_budget: int
    broker_requests_executed: int
    lifecycle_status: str
    custody_status: str
    invocation_completed: bool
    result_container_type: str
    result_payload_class: str
    authentication_error_present: bool
    entitlement_error_present: bool
    protocol_error_present: bool
    raw_output_committed: bool
    raw_output_destroyed: bool
    fixture_admitted: bool = field(default=False, init=False)
    sdk_called: bool = field(default=False, init=False)
    execution_authority: bool = field(default=False, init=False)
    schema_version: str = field(default=TRANSPORT_SCHEMA_VERSION, init=False)

    def valid_for_snapshot_admission(self) -> bool:
        return all(
            (
                _is_safe_identifier(self.transport_receipt_id),
                _is_safe_identifier(self.capture_session_id),
                self.transport_plane == "webull_mcp_custom_composition",
                self.tool_name == _EXPECTED_TOOL,
                self.visible_tool_names == _EXPECTED_VISIBLE_TOOLS,
                self.canonical_argument_field_names == _EXPECTED_CANONICAL_FIELDS,
                self.admitted_argument_field_names == _EXPECTED_ADMITTED_ARGUMENT_FIELDS,
                self.optional_arguments_forwarded is False,
                type(self.broker_request_budget) is int,
                self.broker_request_budget == 1,
                type(self.broker_requests_executed) is int,
                self.broker_requests_executed == 1,
                self.lifecycle_status == "CLOSED",
                self.custody_status == "RAW_DESTROYED",
                self.invocation_completed is True,
                self.result_container_type == FICTIONAL_RESULT_CONTAINER_TYPE,
                self.result_payload_class == "formatted_text",
                self.authentication_error_present is False,
                self.entitlement_error_present is False,
                self.protocol_error_present is False,
                self.raw_output_committed is False,
                self.raw_output_destroyed is True,
                self.fixture_admitted is False,
                self.sdk_called is False,
                self.execution_authority is False,
            )
        )

    def to_dict(self) -> Dict[str, Any]:
        if not self.valid_for_snapshot_admission():
            raise ValueError("invalid transport receipt cannot be serialized")
        return {
            "transport_receipt_id": self.transport_receipt_id,
            "schema_version": self.schema_version,
            "capture_session_id": self.capture_session_id,
            "transport_plane": self.transport_plane,
            "tool_name": self.tool_name,
            "visible_tool_names": list(self.visible_tool_names),
            "canonical_argument_field_names": list(self.canonical_argument_field_names),
            "admitted_argument_field_names": list(self.admitted_argument_field_names),
            "optional_arguments_forwarded": self.optional_arguments_forwarded,
            "broker_request_budget": self.broker_request_budget,
            "broker_requests_executed": self.broker_requests_executed,
            "lifecycle_status": self.lifecycle_status,
            "custody_status": self.custody_status,
            "invocation_completed": self.invocation_completed,
            "result_container_type": self.result_container_type,
            "result_payload_class": self.result_payload_class,
            "authentication_error_present": self.authentication_error_present,
            "entitlement_error_present": self.entitlement_error_present,
            "protocol_error_present": self.protocol_error_present,
            "raw_output_committed": self.raw_output_committed,
            "raw_output_destroyed": self.raw_output_destroyed,
            "fixture_admitted": self.fixture_admitted,
            "sdk_called": self.sdk_called,
            "execution_authority": self.execution_authority,
        }


@dataclass(frozen=True)
class RawWitnessReference:
    raw_reference_id: str
    capture_session_id: str
    capture_started_at: str
    capture_recorded_at: str
    source_plane: str
    tool_name: str
    raw_destroyed: bool
    destruction_verified: bool
    raw_content_retained: bool = field(default=False, init=False)
    repository_path: None = field(default=None, init=False)
    fixture_id: None = field(default=None, init=False)

    def valid_for_snapshot_admission(self) -> bool:
        capture_started_at = _aware_iso8601(self.capture_started_at)
        capture_recorded_at = _aware_iso8601(self.capture_recorded_at)
        return all(
            (
                _is_safe_identifier(self.raw_reference_id),
                _is_safe_identifier(self.capture_session_id),
                capture_started_at is not None,
                capture_recorded_at is not None,
                capture_started_at is not None
                and capture_recorded_at is not None
                and capture_recorded_at >= capture_started_at,
                self.source_plane == "webull_mcp_custom_composition",
                self.tool_name == _EXPECTED_TOOL,
                self.raw_destroyed is True,
                self.destruction_verified is True,
                self.raw_content_retained is False,
                self.repository_path is None,
                self.fixture_id is None,
            )
        )

    def to_dict(self) -> Dict[str, Any]:
        if not self.valid_for_snapshot_admission():
            raise ValueError("invalid raw witness reference cannot be serialized")
        return {
            "raw_reference_id": self.raw_reference_id,
            "capture_session_id": self.capture_session_id,
            "capture_started_at": self.capture_started_at,
            "capture_recorded_at": self.capture_recorded_at,
            "source_plane": self.source_plane,
            "tool_name": self.tool_name,
            "raw_destroyed": self.raw_destroyed,
            "destruction_verified": self.destruction_verified,
            "raw_content_retained": self.raw_content_retained,
            "repository_path": self.repository_path,
            "fixture_id": self.fixture_id,
        }


@dataclass(frozen=True)
class ScrubbedSnapshotDerivative:
    derivative_id: str
    source_package: str
    source_package_version: str
    formatter_shape_id: str
    raw_reference_id: str
    transport_receipt_id: str
    revision_of: Optional[str]
    instrument_symbol: str
    observed_at: Optional[str]
    recorded_at: str
    observed_at_source: str
    broker_field_names: Tuple[str, ...]
    admitted_field_names: Tuple[str, ...]
    rejected_field_names: Tuple[str, ...]
    ambiguous_field_names: Tuple[str, ...]
    market_fields: Mapping[str, Optional[str]]
    null_field_names: Tuple[str, ...]
    unknown_fields: Tuple[str, ...]
    recognized_but_not_admitted_field_names: Tuple[str, ...] = ()
    _construction_seal: InitVar[object] = None
    parse_status: str = "CANDIDATE"
    human_review_status: str = "PENDING"
    sha256_registration: Optional[str] = None
    fixture_admitted: bool = field(default=False, init=False)
    execution_authority: bool = field(default=False, init=False)
    parser_version: str = field(default=PARSER_VERSION, init=False)
    schema_version: str = field(default=DERIVATIVE_SCHEMA_VERSION, init=False)

    def __post_init__(self, _construction_seal: object) -> None:
        if _construction_seal is not _DERIVATIVE_CONSTRUCTION_SEAL:
            raise ValueError("derivative construction is restricted")
        identifiers = (
            self.derivative_id,
            self.raw_reference_id,
            self.transport_receipt_id,
        )
        if not all(_is_safe_identifier(value) for value in identifiers):
            raise ValueError("derivative identifiers are invalid")
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("artifact identifiers must remain distinct")
        if self.revision_of is not None and (
            not _is_safe_identifier(self.revision_of) or self.revision_of in identifiers
        ):
            raise ValueError("revision identity is invalid")
        if self.source_package != WEBULL_MCP_SOURCE_PACKAGE:
            raise ValueError("source package is unsupported")
        fictional_contract = (
            self.source_package_version == FICTIONAL_SOURCE_PACKAGE_VERSION
            and self.formatter_shape_id == FICTIONAL_FORMATTER_SHAPE_ID
        )
        webull_116_contract = (
            self.source_package_version == WEBULL_MCP_SOURCE_PACKAGE_VERSION
            and self.formatter_shape_id == WEBULL_MCP_FORMATTER_SHAPE_ID
        )
        if not (fictional_contract or webull_116_contract):
            raise ValueError("source formatter contract is unsupported")
        if not isinstance(self.instrument_symbol, str) or not _SAFE_SYMBOL.fullmatch(
            self.instrument_symbol
        ):
            raise ValueError("instrument symbol is invalid")
        if not _is_aware_iso8601(self.recorded_at):
            raise ValueError("recorded_at is invalid")
        if self.observed_at is not None and not _is_aware_iso8601(self.observed_at):
            raise ValueError("observed_at is invalid")
        if self.observed_at_source not in {"BROKER_EXPLICIT", "UNAVAILABLE"}:
            raise ValueError("observed_at source is invalid")
        if (self.observed_at is None) != (self.observed_at_source == "UNAVAILABLE"):
            raise ValueError("observed_at source contradicts observed_at")
        expected_broker_fields = (
            _EXPECTED_KEYS if fictional_contract else _WEBULL_BROKER_FIELD_NAMES
        )
        expected_admitted_fields = (
            _EXPECTED_DERIVATIVE_ADMITTED_FIELDS
            if fictional_contract
            else _WEBULL_ADMITTED_FIELD_NAMES
        )
        expected_recognized_not_admitted = (
            ()
            if fictional_contract
            else _WEBULL_RECOGNIZED_NOT_ADMITTED_FIELD_NAMES
        )
        expected_market_fields = (
            _EXPECTED_MARKET_FIELDS if fictional_contract else _WEBULL_MARKET_FIELDS
        )
        if self.broker_field_names != expected_broker_fields:
            raise ValueError("broker field names are unsupported")
        if self.admitted_field_names != expected_admitted_fields:
            raise ValueError("admitted field names are unsupported")
        if (
            self.recognized_but_not_admitted_field_names
            != expected_recognized_not_admitted
        ):
            raise ValueError("recognized non-admitted fields are unsupported")
        if (
            self.rejected_field_names != ()
            or self.ambiguous_field_names != ()
            or self.unknown_fields != ()
        ):
            raise ValueError("candidate contains unresolved fields")
        if (
            not isinstance(self.market_fields, Mapping)
            or set(self.market_fields) != expected_market_fields
        ):
            raise ValueError("market fields are unsupported")
        market_fields = dict(self.market_fields)
        required_string_fields = ("last_price", "bid", "ask", "spread", "volume")
        if fictional_contract:
            required_string_fields = (*required_string_fields, "market_status")
        if any(not isinstance(market_fields[name], str) for name in required_string_fields):
            raise ValueError("market field value type is invalid")
        if fictional_contract:
            if market_fields["delayed"] is not None and not isinstance(
                market_fields["delayed"], str
            ):
                raise ValueError("delayed value type is invalid")
        try:
            last_price = _parse_nonnegative_decimal(market_fields["last_price"])
            bid = _parse_nonnegative_decimal(market_fields["bid"])
            ask = _parse_nonnegative_decimal(market_fields["ask"])
            spread = _parse_nonnegative_decimal(market_fields["spread"])
            volume = _parse_volume(market_fields["volume"])
        except _ParserRefusal as exc:
            raise ValueError("market field value is invalid") from exc
        if Decimal(ask) < Decimal(bid) or spread != str(Decimal(ask) - Decimal(bid)):
            raise ValueError("spread does not match bid and ask")
        if fictional_contract:
            if market_fields["market_status"] not in {
                "OPEN",
                "CLOSED",
                "PRE",
                "AFTER",
                "UNKNOWN",
            }:
                raise ValueError("market status is invalid")
            if market_fields["delayed"] not in {"true", "false", None}:
                raise ValueError("delayed status is invalid")
            expected_null_fields = tuple(
                sorted(name for name, value in market_fields.items() if value is None)
            )
            if self.null_field_names != expected_null_fields:
                raise ValueError("null field names contradict market fields")
        else:
            if self.observed_at is not None or self.observed_at_source != "UNAVAILABLE":
                raise ValueError("Webull formatter does not supply observation time")
            if (
                len(self.null_field_names) != len(set(self.null_field_names))
                or self.null_field_names != tuple(sorted(self.null_field_names))
                or not set(self.null_field_names).issubset(
                    set(_WEBULL_RECOGNIZED_NOT_ADMITTED_FIELD_NAMES)
                )
            ):
                raise ValueError("null field names contradict formatter contract")
        if self.parse_status != "CANDIDATE":
            raise ValueError("parse status is invalid")
        if self.human_review_status not in {"PENDING", "APPROVED"}:
            raise ValueError("human review status is invalid")
        if self.human_review_status == "PENDING" and self.sha256_registration is not None:
            raise ValueError("unapproved derivative cannot have a hash")
        if self.human_review_status == "APPROVED" and not (
            isinstance(self.sha256_registration, str)
            and bool(re.fullmatch(r"[0-9a-f]{64}", self.sha256_registration))
        ):
            raise ValueError("approved derivative hash is invalid")
        object.__setattr__(self, "market_fields", _freeze_mapping(market_fields))
        if self.human_review_status == "APPROVED" and self.sha256_registration != (
            _canonical_sha256(self.to_dict(include_hash=False))
        ):
            raise ValueError("approved derivative hash does not match content")

    def to_dict(self, *, include_hash: bool = True) -> Dict[str, Any]:
        result = {
            "schema_version": self.schema_version,
            "derivative_id": self.derivative_id,
            "parser_version": self.parser_version,
            "source_package": self.source_package,
            "source_package_version": self.source_package_version,
            "formatter_shape_id": self.formatter_shape_id,
            "raw_reference_id": self.raw_reference_id,
            "transport_receipt_id": self.transport_receipt_id,
            "revision_of": self.revision_of,
            "instrument": {"symbol": self.instrument_symbol, "asset_class": "stock"},
            "observed_at": self.observed_at,
            "recorded_at": self.recorded_at,
            "observed_at_source": self.observed_at_source,
            "broker_field_names": list(self.broker_field_names),
            "admitted_field_names": list(self.admitted_field_names),
            "rejected_field_names": list(self.rejected_field_names),
            "ambiguous_field_names": list(self.ambiguous_field_names),
            "recognized_but_not_admitted_field_names": list(
                self.recognized_but_not_admitted_field_names
            ),
            "market_fields": dict(self.market_fields),
            "null_field_names": list(self.null_field_names),
            "unknown_fields": list(self.unknown_fields),
            "parse_status": self.parse_status,
            "human_review_status": self.human_review_status,
            "fixture_admitted": self.fixture_admitted,
            "execution_authority": self.execution_authority,
        }
        if self.human_review_status == "APPROVED" and self.sha256_registration != (
            _canonical_sha256(result)
        ):
            raise ValueError("approved derivative integrity check failed")
        if include_hash:
            result["sha256_registration"] = self.sha256_registration
        return result


@dataclass(frozen=True)
class AdmissionRefusal:
    failure_class: str
    source_package: str
    source_package_version: str
    formatter_shape_id: str
    raw_reference_id: str
    transport_receipt_id: str
    parse_status: str = field(default="REFUSED", init=False)
    admitted_field_names: Tuple[str, ...] = field(default=(), init=False)
    rejected_field_names: Tuple[str, ...] = field(default=(), init=False)
    ambiguous_field_names: Tuple[str, ...] = field(default=(), init=False)
    observed_at_source: str = field(default="UNAVAILABLE", init=False)
    parser_version: str = field(default=PARSER_VERSION, init=False)
    execution_authority: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.failure_class not in FAILURE_CLASSES:
            raise ValueError("unsupported admission failure class")
        if self.source_package not in {WEBULL_MCP_SOURCE_PACKAGE, "UNSUPPORTED"}:
            raise ValueError("unsafe refusal source package")
        if self.source_package_version not in {
            FICTIONAL_SOURCE_PACKAGE_VERSION,
            WEBULL_MCP_SOURCE_PACKAGE_VERSION,
            "UNSUPPORTED",
        }:
            raise ValueError("unsafe refusal source package version")
        if self.formatter_shape_id not in {
            FICTIONAL_FORMATTER_SHAPE_ID,
            WEBULL_MCP_FORMATTER_SHAPE_ID,
            "UNSUPPORTED",
        }:
            raise ValueError("unsafe refusal formatter shape")
        if not _is_safe_identifier(self.raw_reference_id):
            raise ValueError("unsafe refusal raw-reference identity")
        if not _is_safe_identifier(self.transport_receipt_id):
            raise ValueError("unsafe refusal transport-receipt identity")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parser_version": self.parser_version,
            "source_package": self.source_package,
            "source_package_version": self.source_package_version,
            "formatter_shape_id": self.formatter_shape_id,
            "parse_status": self.parse_status,
            "failure_class": self.failure_class,
            "admitted_field_names": [],
            "rejected_field_names": [],
            "ambiguous_field_names": [],
            "observed_at_source": self.observed_at_source,
            "raw_reference_id": self.raw_reference_id,
            "transport_receipt_id": self.transport_receipt_id,
            "execution_authority": self.execution_authority,
        }


AdmissionOutcome = Union[ScrubbedSnapshotDerivative, AdmissionRefusal]


class _ParserRefusal(ValueError):
    def __init__(self, failure_class: str) -> None:
        super().__init__(failure_class)
        self.failure_class = failure_class


def _refusal(
    failure_class: str,
    *,
    source_package: str,
    source_package_version: str,
    formatter_shape_id: str,
    raw_reference_id: str,
    transport_receipt_id: str,
) -> AdmissionRefusal:
    return AdmissionRefusal(
        failure_class=failure_class,
        source_package=(
            WEBULL_MCP_SOURCE_PACKAGE
            if source_package == WEBULL_MCP_SOURCE_PACKAGE
            else "UNSUPPORTED"
        ),
        source_package_version=(
            source_package_version
            if source_package_version
            in {FICTIONAL_SOURCE_PACKAGE_VERSION, WEBULL_MCP_SOURCE_PACKAGE_VERSION}
            else "UNSUPPORTED"
        ),
        formatter_shape_id=(
            formatter_shape_id
            if formatter_shape_id
            in {FICTIONAL_FORMATTER_SHAPE_ID, WEBULL_MCP_FORMATTER_SHAPE_ID}
            else "UNSUPPORTED"
        ),
        raw_reference_id=_safe_identifier(raw_reference_id),
        transport_receipt_id=_safe_identifier(transport_receipt_id),
    )


def _parse_nonnegative_decimal(value: str) -> str:
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise _ParserRefusal("VALUE_TYPE_INVALID") from exc
    if not parsed.is_finite() or parsed < 0:
        raise _ParserRefusal("VALUE_TYPE_INVALID")
    return value


def _parse_volume(value: str) -> str:
    if not value.isdigit():
        raise _ParserRefusal("VALUE_TYPE_INVALID")
    return value


def _parse_timestamp(value: str) -> Tuple[Optional[str], str]:
    if value == "NULL":
        return None, "UNAVAILABLE"
    if not value:
        raise _ParserRefusal("TIMESTAMP_UNAVAILABLE")
    candidate = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise _ParserRefusal("TIMESTAMP_UNAVAILABLE") from exc
    if parsed.tzinfo is None:
        raise _ParserRefusal("TIMESTAMP_UNAVAILABLE")
    return value, "BROKER_EXPLICIT"


def _parse_fictional_content(content: str, *, expected_symbol: str) -> Dict[str, Any]:
    lines = content.splitlines()
    if len(lines) != len(_EXPECTED_KEYS) + 2:
        raise _ParserRefusal("REQUIRED_FIELD_MISSING")
    if lines[0] != FICTIONAL_HEADER or lines[-1] != "END":
        raise _ParserRefusal("UNKNOWN_FORMATTER_SHAPE")

    values: Dict[str, str] = {}
    seen_keys = []
    for line in lines[1:-1]:
        if line.count("=") != 1:
            raise _ParserRefusal("AMBIGUOUS_FIELD")
        key, value = line.split("=", 1)
        if not key or key in values:
            raise _ParserRefusal("AMBIGUOUS_FIELD")
        seen_keys.append(key)
        values[key] = value
    if tuple(seen_keys) != _EXPECTED_KEYS:
        raise _ParserRefusal("AMBIGUOUS_FIELD")
    if values["symbol"] != expected_symbol:
        raise _ParserRefusal("SYMBOL_MISMATCH")

    last_price = _parse_nonnegative_decimal(values["last_price"])
    bid = _parse_nonnegative_decimal(values["bid"])
    ask = _parse_nonnegative_decimal(values["ask"])
    if Decimal(ask) < Decimal(bid):
        raise _ParserRefusal("VALUE_TYPE_INVALID")
    volume = _parse_volume(values["volume"])
    observed_at, observed_at_source = _parse_timestamp(values["observed_at"])
    if values["market_status"] not in {"OPEN", "CLOSED", "PRE", "AFTER", "UNKNOWN"}:
        raise _ParserRefusal("VALUE_TYPE_INVALID")
    if values["delayed"] not in {"true", "false", "NULL"}:
        raise _ParserRefusal("VALUE_TYPE_INVALID")

    spread = str(Decimal(ask) - Decimal(bid))
    market_fields = {
        "last_price": last_price,
        "bid": bid,
        "ask": ask,
        "spread": spread,
        "volume": volume,
        "market_status": values["market_status"],
        "delayed": None if values["delayed"] == "NULL" else values["delayed"],
    }
    null_fields = tuple(sorted(key for key, value in market_fields.items() if value is None))
    return {
        "observed_at": observed_at,
        "observed_at_source": observed_at_source,
        "market_fields": market_fields,
        "null_field_names": null_fields,
    }


def _source_hashes_match(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    try:
        supplied = dict(value)
    except Exception:
        return False
    return supplied == dict(WEBULL_MCP_SOURCE_FILE_HASHES) and all(
        isinstance(key, str) and isinstance(digest, str)
        for key, digest in supplied.items()
    )


def _admitted_arguments_match(value: Any, *, expected_symbol: str) -> bool:
    if not isinstance(value, Mapping):
        return False
    try:
        supplied = dict(value)
    except Exception:
        return False
    return (
        set(supplied) == {"symbols"}
        and type(supplied["symbols"]) is str
        and supplied["symbols"] == expected_symbol
    )


def _aligned_value(field_value: str, width: int) -> str:
    value = field_value.lstrip(" ")
    if (
        not value
        or any(character.isspace() for character in value)
        or field_value != value.rjust(width)
    ):
        raise _ParserRefusal("FIELD_LAYOUT_MISMATCH")
    return value


def _match_webull_line(
    pattern: re.Pattern[str],
    line: str,
    widths: Mapping[str, int],
) -> Dict[str, str]:
    match = pattern.fullmatch(line)
    if match is None:
        raise _ParserRefusal("FIELD_LAYOUT_MISMATCH")
    return {
        name: _aligned_value(match.group(name), width)
        for name, width in widths.items()
    }


def _validate_formatter_decimal(
    value: str,
    *,
    required: bool,
    nonnegative: bool,
) -> Optional[str]:
    if value == "N/A":
        if required:
            raise _ParserRefusal("REQUIRED_FIELD_MISSING")
        return None
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise _ParserRefusal("VALUE_TYPE_INVALID") from exc
    if not parsed.is_finite() or (nonnegative and parsed < 0):
        raise _ParserRefusal("VALUE_TYPE_INVALID")
    return value


def _validate_formatter_whole(
    value: str,
    *,
    required: bool,
) -> Optional[str]:
    if value == "N/A":
        if required:
            raise _ParserRefusal("REQUIRED_FIELD_MISSING")
        return None
    if not value.isdigit():
        raise _ParserRefusal("VALUE_TYPE_INVALID")
    return value


def _parse_webull_mcp_116_content(
    content: str,
    *,
    expected_symbol: str,
) -> Dict[str, Any]:
    lines = content.split("\n")
    if not lines or lines[0] != WEBULL_MCP_US_DISCLAIMER_LINE:
        raise _ParserRefusal("DISCLAIMER_MISMATCH")
    if len(lines) < 2 or lines[1] != "":
        raise _ParserRefusal("DISCLAIMER_MISMATCH")
    if any(
        marker in line
        for line in lines
        for marker in ("ExtHr Price:", "OVN Price:", "OVN Bid:", "OVN Ask:")
    ):
        raise _ParserRefusal("OPTIONAL_SECTION_UNSUPPORTED")
    if (
        sum(line == WEBULL_MCP_HEADER for line in lines) > 1
        or sum("  Price:" in line and "PreClose:" in line for line in lines) > 1
    ):
        raise _ParserRefusal("MULTI_SYMBOL_RESPONSE")
    if len(lines) != 7:
        raise _ParserRefusal("LINE_COUNT_MISMATCH")
    if lines[2] != WEBULL_MCP_HEADER:
        raise _ParserRefusal("FIELD_LAYOUT_MISMATCH")

    primary = _match_webull_line(
        _WEBULL_PRIMARY_LINE,
        lines[3],
        {
            "symbol": 8,
            "price": 10,
            "pre_close": 10,
            "change": 8,
            "change_ratio": 8,
        },
    )
    ohlcv = _match_webull_line(
        _WEBULL_OHLCV_LINE,
        lines[4],
        {"open": 10, "high": 10, "low": 10, "close": 10, "volume": 12},
    )
    quotes = _match_webull_line(
        _WEBULL_QUOTE_LINE,
        lines[5],
        {"bid": 10, "bid_size": 6, "ask": 10, "ask_size": 6},
    )
    fundamentals = _match_webull_line(
        _WEBULL_FUNDAMENTALS_LINE,
        lines[6],
        {"turnover": 12, "eps": 8, "eps_ttm": 8, "lot_size": 6, "bps": 8},
    )
    if primary["symbol"] != expected_symbol:
        raise _ParserRefusal("SYMBOL_MISMATCH")

    last_price = _validate_formatter_decimal(
        primary["price"], required=True, nonnegative=True
    )
    bid = _validate_formatter_decimal(quotes["bid"], required=True, nonnegative=True)
    ask = _validate_formatter_decimal(quotes["ask"], required=True, nonnegative=True)
    volume = _validate_formatter_whole(ohlcv["volume"], required=True)
    assert last_price is not None and bid is not None and ask is not None
    assert volume is not None
    if Decimal(ask) < Decimal(bid):
        raise _ParserRefusal("VALUE_TYPE_INVALID")

    nullable_values = {
        "pre_close": _validate_formatter_decimal(
            primary["pre_close"], required=False, nonnegative=True
        ),
        "change": _validate_formatter_decimal(
            primary["change"], required=False, nonnegative=False
        ),
        "change_ratio": _validate_formatter_decimal(
            primary["change_ratio"], required=False, nonnegative=False
        ),
        "open": _validate_formatter_decimal(
            ohlcv["open"], required=False, nonnegative=True
        ),
        "high": _validate_formatter_decimal(
            ohlcv["high"], required=False, nonnegative=True
        ),
        "low": _validate_formatter_decimal(
            ohlcv["low"], required=False, nonnegative=True
        ),
        "close": _validate_formatter_decimal(
            ohlcv["close"], required=False, nonnegative=True
        ),
        "bid_size": _validate_formatter_whole(quotes["bid_size"], required=False),
        "ask_size": _validate_formatter_whole(quotes["ask_size"], required=False),
        "turnover": _validate_formatter_decimal(
            fundamentals["turnover"], required=False, nonnegative=True
        ),
        "eps": _validate_formatter_decimal(
            fundamentals["eps"], required=False, nonnegative=False
        ),
        "eps_ttm": _validate_formatter_decimal(
            fundamentals["eps_ttm"], required=False, nonnegative=False
        ),
        "lot_size": _validate_formatter_whole(
            fundamentals["lot_size"], required=False
        ),
        "bps": _validate_formatter_decimal(
            fundamentals["bps"], required=False, nonnegative=False
        ),
    }
    if all(
        nullable_values[name] is None
        for name in ("turnover", "eps", "eps_ttm", "lot_size", "bps")
    ):
        raise _ParserRefusal("FIELD_LAYOUT_MISMATCH")

    return {
        "observed_at": None,
        "observed_at_source": "UNAVAILABLE",
        "market_fields": {
            "last_price": last_price,
            "bid": bid,
            "ask": ask,
            "spread": str(Decimal(ask) - Decimal(bid)),
            "volume": volume,
        },
        "null_field_names": tuple(
            sorted(name for name, value in nullable_values.items() if value is None)
        ),
        "broker_field_names": _WEBULL_BROKER_FIELD_NAMES,
        "admitted_field_names": _WEBULL_ADMITTED_FIELD_NAMES,
        "recognized_but_not_admitted_field_names": (
            _WEBULL_RECOGNIZED_NOT_ADMITTED_FIELD_NAMES
        ),
    }


def _extract_original_mcp_result(result_container: Any) -> str:
    """Validate the original low-level MCP envelope before reading formatter text."""

    expected_result_type = _MCP_CALL_TOOL_RESULT_TYPE
    if expected_result_type is None:
        try:
            from mcp.types import CallToolResult as expected_result_type
        except Exception as exc:
            raise _ParserRefusal("RESULT_CONTAINER_MISSING") from exc
    if type(result_container) is not expected_result_type:
        raise _ParserRefusal("RESULT_CONTAINER_MISSING")

    missing = object()
    try:
        structured_content = getattr(result_container, "structuredContent", missing)
        error_flag = getattr(result_container, "isError", missing)
        snake_structured_content = getattr(
            result_container,
            "structured_content",
            missing,
        )
        snake_error_flag = getattr(result_container, "is_error", missing)
        top_level_result = getattr(result_container, "result", missing)
        parsed_data = getattr(result_container, "data", missing)
        extracted_result = getattr(
            result_container,
            "structured_content_result",
            missing,
        )
        model_extra = getattr(result_container, "model_extra", missing)
    except Exception as exc:
        raise _ParserRefusal("RESULT_CONTAINER_MISSING") from exc

    if any(
        value is not missing
        for value in (
            snake_structured_content,
            snake_error_flag,
            top_level_result,
            parsed_data,
            extracted_result,
        )
    ):
        raise _ParserRefusal("AMBIGUOUS_FIELD")
    if model_extra is not missing and model_extra is not None:
        if not isinstance(model_extra, Mapping):
            raise _ParserRefusal("VALUE_TYPE_INVALID")
        if model_extra:
            raise _ParserRefusal("AMBIGUOUS_FIELD")
    if error_flag is not missing and type(error_flag) is not bool:
        raise _ParserRefusal("VALUE_TYPE_INVALID")
    if error_flag is True:
        raise _ParserRefusal("RESULT_CONTAINER_MISSING")
    if structured_content is missing or structured_content is None:
        raise _ParserRefusal("STRUCTURED_CONTENT_MISSING")
    if not isinstance(structured_content, Mapping):
        raise _ParserRefusal("VALUE_TYPE_INVALID")
    try:
        structured_snapshot = dict(structured_content)
    except Exception as exc:
        raise _ParserRefusal("VALUE_TYPE_INVALID") from exc
    if "result" not in structured_snapshot:
        raise _ParserRefusal("RESULT_CONTAINER_MISSING")
    if set(structured_snapshot) != {"result"}:
        raise _ParserRefusal("AMBIGUOUS_FIELD")

    formatter_result = structured_snapshot["result"]
    if not isinstance(formatter_result, str):
        raise _ParserRefusal("VALUE_TYPE_INVALID")
    if len(formatter_result) > 10_000:
        raise _ParserRefusal("VALUE_TYPE_INVALID")
    return formatter_result


def admit_formatted_snapshot(
    *,
    transport_receipt: TransportReceipt,
    raw_reference: RawWitnessReference,
    derivative_id: str,
    expected_symbol: str,
    source_package: str,
    source_package_version: str,
    formatter_shape_id: str,
    result_container: Any,
    source_file_hashes: Optional[Mapping[str, str]] = None,
    admitted_arguments: Optional[Mapping[str, Any]] = None,
    revision_of: Optional[str] = None,
) -> AdmissionOutcome:
    """Build a scrubbed candidate or return a value-free categorical refusal."""

    transport_id = getattr(transport_receipt, "transport_receipt_id", "")
    raw_id = getattr(raw_reference, "raw_reference_id", "")
    refusal_args = {
        "source_package": source_package,
        "source_package_version": source_package_version,
        "formatter_shape_id": formatter_shape_id,
        "raw_reference_id": raw_id,
        "transport_receipt_id": transport_id,
    }
    try:
        if not isinstance(transport_receipt, TransportReceipt) or not transport_receipt.valid_for_snapshot_admission():
            return _refusal("TRANSPORT_RECEIPT_INVALID", **refusal_args)
        if not isinstance(raw_reference, RawWitnessReference) or not raw_reference.valid_for_snapshot_admission():
            return _refusal("RAW_REFERENCE_INVALID", **refusal_args)
        if transport_receipt.capture_session_id != raw_reference.capture_session_id:
            return _refusal("RAW_REFERENCE_INVALID", **refusal_args)
        structured_content_result = _extract_original_mcp_result(result_container)
        if _SECRET_PATTERN.search(structured_content_result):
            return _refusal("SECRET_PATTERN_PRESENT", **refusal_args)
        if _IDENTITY_PATTERN.search(structured_content_result):
            return _refusal("IDENTITY_PATTERN_PRESENT", **refusal_args)
        if source_package != WEBULL_MCP_SOURCE_PACKAGE:
            return _refusal("UNSUPPORTED_PACKAGE_VERSION", **refusal_args)
        if source_package_version not in {
            FICTIONAL_SOURCE_PACKAGE_VERSION,
            WEBULL_MCP_SOURCE_PACKAGE_VERSION,
        }:
            return _refusal("UNSUPPORTED_PACKAGE_VERSION", **refusal_args)
        fictional_contract = (
            source_package_version == FICTIONAL_SOURCE_PACKAGE_VERSION
            and formatter_shape_id == FICTIONAL_FORMATTER_SHAPE_ID
        )
        webull_116_contract = (
            source_package_version == WEBULL_MCP_SOURCE_PACKAGE_VERSION
            and formatter_shape_id == WEBULL_MCP_FORMATTER_SHAPE_ID
        )
        if not (fictional_contract or webull_116_contract):
            return _refusal("UNKNOWN_FORMATTER_SHAPE", **refusal_args)
        if not isinstance(expected_symbol, str) or not _SAFE_SYMBOL.fullmatch(expected_symbol):
            return _refusal("SYMBOL_MISMATCH", **refusal_args)
        if webull_116_contract:
            if not _source_hashes_match(source_file_hashes):
                return _refusal("SOURCE_HASH_MISMATCH", **refusal_args)
            if not _admitted_arguments_match(
                admitted_arguments,
                expected_symbol=expected_symbol,
            ):
                return _refusal("FIELD_LAYOUT_MISMATCH", **refusal_args)
        if not _is_safe_identifier(derivative_id):
            return _refusal("VALUE_TYPE_INVALID", **refusal_args)
        if derivative_id in {raw_reference.raw_reference_id, transport_receipt.transport_receipt_id}:
            return _refusal("VALUE_TYPE_INVALID", **refusal_args)
        if revision_of is not None and (
            not _is_safe_identifier(revision_of) or revision_of == derivative_id
        ):
            return _refusal("VALUE_TYPE_INVALID", **refusal_args)
        if _FORBIDDEN_VOCABULARY.search(structured_content_result):
            return _refusal("AMBIGUOUS_FIELD", **refusal_args)

        if fictional_contract:
            parsed = _parse_fictional_content(
                structured_content_result,
                expected_symbol=expected_symbol,
            )
            broker_field_names = _EXPECTED_KEYS
            admitted_field_names = _EXPECTED_DERIVATIVE_ADMITTED_FIELDS
            recognized_but_not_admitted_field_names: Tuple[str, ...] = ()
        else:
            parsed = _parse_webull_mcp_116_content(
                structured_content_result,
                expected_symbol=expected_symbol,
            )
            broker_field_names = parsed["broker_field_names"]
            admitted_field_names = parsed["admitted_field_names"]
            recognized_but_not_admitted_field_names = parsed[
                "recognized_but_not_admitted_field_names"
            ]
        return ScrubbedSnapshotDerivative(
            derivative_id=derivative_id,
            source_package=source_package,
            source_package_version=source_package_version,
            formatter_shape_id=formatter_shape_id,
            raw_reference_id=raw_reference.raw_reference_id,
            transport_receipt_id=transport_receipt.transport_receipt_id,
            revision_of=revision_of,
            instrument_symbol=expected_symbol,
            observed_at=parsed["observed_at"],
            recorded_at=raw_reference.capture_recorded_at,
            observed_at_source=parsed["observed_at_source"],
            broker_field_names=broker_field_names,
            admitted_field_names=admitted_field_names,
            rejected_field_names=(),
            ambiguous_field_names=(),
            market_fields=parsed["market_fields"],
            null_field_names=parsed["null_field_names"],
            unknown_fields=(),
            recognized_but_not_admitted_field_names=(
                recognized_but_not_admitted_field_names
            ),
            _construction_seal=_DERIVATIVE_CONSTRUCTION_SEAL,
        )
    except _ParserRefusal as exc:
        return _refusal(exc.failure_class, **refusal_args)
    except Exception:
        return _refusal("PARSER_INTERNAL_ERROR", **refusal_args)


def register_human_approved_derivative(
    derivative: ScrubbedSnapshotDerivative,
    *,
    human_review_authorized: bool,
) -> AdmissionOutcome:
    """Register SHA-256 only after an explicit human-review authorization."""

    if (
        not isinstance(derivative, ScrubbedSnapshotDerivative)
        or human_review_authorized is not True
        or derivative.human_review_status != "PENDING"
        or derivative.sha256_registration is not None
    ):
        return _refusal(
            "HUMAN_REVIEW_REQUIRED",
            source_package=getattr(derivative, "source_package", ""),
            source_package_version=getattr(derivative, "source_package_version", ""),
            formatter_shape_id=getattr(derivative, "formatter_shape_id", ""),
            raw_reference_id=getattr(derivative, "raw_reference_id", ""),
            transport_receipt_id=getattr(derivative, "transport_receipt_id", ""),
        )
    try:
        approved_payload = derivative.to_dict(include_hash=False)
        approved_payload["human_review_status"] = "APPROVED"
        digest = _canonical_sha256(approved_payload)
        return replace(
            derivative,
            human_review_status="APPROVED",
            sha256_registration=digest,
            _construction_seal=_DERIVATIVE_CONSTRUCTION_SEAL,
        )
    except Exception:
        return _refusal(
            "PARSER_INTERNAL_ERROR",
            source_package=derivative.source_package,
            source_package_version=derivative.source_package_version,
            formatter_shape_id=derivative.formatter_shape_id,
            raw_reference_id=derivative.raw_reference_id,
            transport_receipt_id=derivative.transport_receipt_id,
        )
