"""selfbull.observation_parser — SELFBULL-002 · manual observation validation.

Validates and normalizes ONE manually observed market record (operator
reading the Webull browser interface and typing values by hand) into the
sealed ``MarketObservationEnvelope`` shape from ``selfbull.contracts``.

Capture mode: MANUAL_BROWSER_OBSERVATION. This module performs no network
call, reads no credential, contacts no broker, and never fabricates a value
the operator did not supply. Missing optional fields stay ``None``.
Standard library only. No import from SELFQUANT or RBHCB.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any, Dict, List, Optional

from selfbull.contracts import SCHEMA_VERSION, MarketObservationEnvelope

CAPTURE_MODE = "MANUAL_BROWSER_OBSERVATION"
MANUAL_SOURCE = "webull_browser_manual"

REQUIRED_FIELDS = ("timestamp_et", "symbol", "last_price", "source")

# Optional fields, in canonical order. Missing values are None — never 0,
# never "n/a", never "unknown".
OPTIONAL_FIELDS = (
    "day_open", "day_high", "day_low", "previous_close",
    "volume", "relative_volume", "bid", "ask", "spread",
    "implied_volatility", "expected_move",
    "call_wall", "put_wall",
    "largest_call_volume_strike", "largest_put_volume_strike",
    "session", "notes",
)

ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS

# Prices that must be strictly positive when present.
_POSITIVE_PRICE_FIELDS = (
    "last_price", "day_open", "day_high", "day_low", "previous_close",
    "call_wall", "put_wall",
    "largest_call_volume_strike", "largest_put_volume_strike",
)
# Non-negative numerics (zero is semantically valid: a zero bid, zero
# volume in the first observed second, a locked market's zero spread).
_NON_NEGATIVE_FIELDS = (
    "bid", "ask", "spread", "volume", "relative_volume",
    "implied_volatility", "expected_move",
)
_NUMERIC_FIELDS = _POSITIVE_PRICE_FIELDS + _NON_NEGATIVE_FIELDS

_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.\-^]{1,12}$")

# A supplied spread that differs from (ask - bid) by more than one cent
# (plus float epsilon) is a material contradiction.
SPREAD_CONFLICT_TOLERANCE = 0.0101

# Reject timestamps more than this far ahead of "now" (clock-skew allowance).
FUTURE_SKEW_ALLOWANCE = timedelta(minutes=5)

VALID = "valid"
CONFLICTED = "conflicted"
INVALID = "invalid"


class _FallbackEastern(tzinfo):
    """US Eastern with the post-2007 DST rule (second Sunday of March to
    first Sunday of November), used only when the host has no IANA tzdata.
    Wall-clock interpretation only — good enough for observation stamps."""

    def _dst_active(self, dt: datetime) -> bool:
        def nth_sunday(year: int, month: int, n: int) -> datetime:
            d = datetime(year, month, 1)
            offset = (6 - d.weekday()) % 7 + (n - 1) * 7
            return d + timedelta(days=offset)

        start = nth_sunday(dt.year, 3, 2).replace(hour=2)
        end = nth_sunday(dt.year, 11, 1).replace(hour=2)
        return start <= dt.replace(tzinfo=None) < end

    def utcoffset(self, dt):
        return timedelta(hours=-4) if self._dst_active(dt) else timedelta(hours=-5)

    def dst(self, dt):
        return timedelta(hours=1) if self._dst_active(dt) else timedelta(0)

    def tzname(self, dt):
        return "EDT" if self._dst_active(dt) else "EST"


def eastern_tz() -> tzinfo:
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/New_York")
    except Exception:                                    # no tzdata on host
        return _FallbackEastern()


@dataclass
class ParsedObservation:
    """Validation outcome for one manual record. ``normalized`` carries
    JSON-safe values (numbers, strings, None). ``raw`` preserves the
    operator's input exactly as received, stringified."""
    raw: Dict[str, Any]
    normalized: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    validation_status: str = INVALID

    @property
    def is_valid(self) -> bool:
        return self.validation_status == VALID


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _parse_timestamp_et(raw: Any, errors: List[str], *, now: Optional[datetime] = None) -> Optional[str]:
    """Parse ISO-8601 or 'YYYY-MM-DD HH:MM:SS', interpret as US Eastern
    unless an explicit offset is supplied, and normalize to ISO-8601 with
    timezone offset. Never substitutes 'now' for a missing value."""
    if _is_blank(raw):
        errors.append("timestamp_et is required and was not supplied")
        return None
    text = str(raw).strip()
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        errors.append(f"timestamp_et is not ISO-8601 or 'YYYY-MM-DD HH:MM:SS': {text!r}")
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=eastern_tz())
    reference = now or datetime.now(timezone.utc)
    if dt > reference + FUTURE_SKEW_ALLOWANCE:
        errors.append(
            f"timestamp_et {dt.isoformat()} is materially in the future "
            f"relative to {reference.isoformat()}"
        )
        return None
    if dt.year < 1971:
        errors.append(f"timestamp_et {dt.isoformat()} predates any plausible observation")
        return None
    return dt.isoformat()


def _parse_symbol(raw: Any, errors: List[str]) -> Optional[str]:
    if _is_blank(raw):
        errors.append("symbol is required and was not supplied")
        return None
    symbol = str(raw).strip().upper()
    if not _SYMBOL_PATTERN.match(symbol):
        errors.append(f"symbol contains unsafe or invalid characters: {raw!r}")
        return None
    return symbol


def _parse_number(name: str, raw: Any, errors: List[str]) -> Optional[float]:
    """Accept int, float, or decimal string. Reject NaN, infinity, and
    malformed strings. Returns a JSON-safe float (or int passthrough as
    float) — never fabricates."""
    if _is_blank(raw):
        return None
    if isinstance(raw, bool):
        errors.append(f"{name} must be numeric, got boolean {raw!r}")
        return None
    try:
        value = float(str(raw).strip()) if not isinstance(raw, (int, float)) else float(raw)
    except (ValueError, TypeError):
        errors.append(f"{name} is not a valid number: {raw!r}")
        return None
    if math.isnan(value) or math.isinf(value):
        errors.append(f"{name} must be finite, got {raw!r}")
        return None
    if name in _POSITIVE_PRICE_FIELDS and value <= 0:
        errors.append(f"{name} must be a positive price, got {value}")
        return None
    if name in _NON_NEGATIVE_FIELDS and value < 0:
        errors.append(f"{name} must not be negative, got {value}")
        return None
    return value


def _stringify_raw(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Preserve the operator's input as evidence, JSON-safe."""
    return {k: (None if v is None else str(v)) for k, v in raw.items()}


def parse_observation(raw: Dict[str, Any], *, now: Optional[datetime] = None) -> ParsedObservation:
    """Validate and normalize one raw manual record (e.g. a CSV row dict).

    Returns a ParsedObservation whose validation_status is one of:
      valid      — every check passed
      conflicted — internally contradictory operator evidence (spread vs
                   bid/ask, price outside day range); supplied values are
                   preserved, never overwritten
      invalid    — a required field is missing/unparseable or a value is
                   malformed
    """
    result = ParsedObservation(raw=_stringify_raw(raw))
    errors = result.errors
    conflicts: List[str] = []

    unknown = sorted(set(raw) - set(ALL_FIELDS))
    if unknown:
        result.warnings.append(f"unrecognized fields ignored: {', '.join(unknown)}")

    norm: Dict[str, Any] = {}
    norm["timestamp_et"] = _parse_timestamp_et(raw.get("timestamp_et"), errors, now=now)
    norm["symbol"] = _parse_symbol(raw.get("symbol"), errors)

    source_raw = raw.get("source")
    if _is_blank(source_raw):
        errors.append("source is required and was not supplied")
        norm["source"] = None
    elif str(source_raw).strip() != MANUAL_SOURCE:
        errors.append(
            f"source must be {MANUAL_SOURCE!r} in manual browser-observation "
            f"mode, got {str(source_raw).strip()!r}"
        )
        norm["source"] = str(source_raw).strip()
    else:
        norm["source"] = MANUAL_SOURCE

    for name in _NUMERIC_FIELDS:
        norm[name] = _parse_number(name, raw.get(name), errors)
    if norm["last_price"] is None and _is_blank(raw.get("last_price")):
        errors.append("last_price is required and was not supplied")

    session_raw = raw.get("session")
    norm["session"] = None if _is_blank(session_raw) else str(session_raw).strip().lower()
    notes_raw = raw.get("notes")
    norm["notes"] = None if _is_blank(notes_raw) else str(notes_raw).strip()

    # ── Spread: derive only from evidence, never overwrite it ────────────
    bid, ask, supplied_spread = norm["bid"], norm["ask"], norm["spread"]
    if bid is not None and ask is not None:
        calculated = round(ask - bid, 6)
        if calculated < 0:
            conflicts.append(f"ask ({ask}) is below bid ({bid}) — crossed quote recorded as observed")
        if supplied_spread is None:
            norm["spread"] = calculated if calculated >= 0 else None
        elif abs(supplied_spread - calculated) > SPREAD_CONFLICT_TOLERANCE:
            conflicts.append(
                f"supplied spread {supplied_spread} contradicts calculated "
                f"spread (ask minus bid) {calculated}; supplied value preserved"
            )

    # ── Day-range consistency ─────────────────────────────────────────────
    low, high, last, opn = norm["day_low"], norm["day_high"], norm["last_price"], norm["day_open"]
    if low is not None and high is not None and low > high:
        conflicts.append(f"day_low ({low}) exceeds day_high ({high})")
    if low is not None and high is not None and last is not None and not (low <= last <= high):
        conflicts.append(f"last_price ({last}) is outside day range [{low}, {high}]")
    if low is not None and high is not None and opn is not None and not (low <= opn <= high):
        conflicts.append(f"day_open ({opn}) is outside day range [{low}, {high}]")

    result.normalized = norm
    result.missing_fields = [f for f in OPTIONAL_FIELDS if norm.get(f) is None]
    result.errors = errors + conflicts
    if errors:
        result.validation_status = INVALID
    elif conflicts:
        result.validation_status = CONFLICTED
    else:
        result.validation_status = VALID
    return result


def build_envelope(parsed: ParsedObservation) -> MarketObservationEnvelope:
    """Wrap a parsed observation in the sealed broker-neutral envelope.

    ``observed_at`` is the normalized Eastern-Time ISO-8601 stamp with
    offset. No execution-authority field exists on this envelope, and none
    is added — an observation is evidence, never an instruction."""
    norm = parsed.normalized
    quote = {
        k: norm.get(k)
        for k in (
            "last_price", "day_open", "day_high", "day_low", "previous_close",
            "volume", "relative_volume", "bid", "ask", "spread",
            "implied_volatility", "expected_move", "call_wall", "put_wall",
            "largest_call_volume_strike", "largest_put_volume_strike",
        )
    }
    return MarketObservationEnvelope(
        broker="webull",
        observed_at=norm.get("timestamp_et") or "",
        instrument={"symbol": norm.get("symbol"), "instrument_type": None},
        source=MANUAL_SOURCE,
        quote=quote,
        session=norm.get("session"),
        freshness=norm.get("timestamp_et"),
        evidence={
            "capture_mode": CAPTURE_MODE,
            "raw_input": parsed.raw,
            "validation_status": parsed.validation_status,
            "validation_errors": list(parsed.errors),
            "validation_warnings": list(parsed.warnings),
            "missing_fields": list(parsed.missing_fields),
            "operator_notes": norm.get("notes"),
            "network_call": False,
        },
        schema_version=SCHEMA_VERSION,
    )
