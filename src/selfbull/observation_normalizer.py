"""SELFBULL-003 manual observation normalizer.

Normalization here means shaping human-supplied evidence into the structured
memory schema. It does not fetch, scrape, infer missing values, or calculate a
trading view.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from selfbull.observation_schema import (
    MARKET_STATE_FIELDS,
    HUMAN_OBSERVED_CONFIDENCE,
    MANUAL_OBSERVATION_TYPE,
    ObservationInstrument,
    ObservationSource,
    StructuredObservation,
)

_TOP_LEVEL_FIELDS = {
    "observation_id",
    "observed_at",
    "recorded_at",
    "observer",
    "source",
    "instrument",
    "market_state",
    "observation_type",
    "confidence",
    "unknown_fields",
    "notes",
}


def _blank_to_none(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def _number_or_none(value: Any) -> Optional[float]:
    value = _blank_to_none(value)
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"market value must be numeric or null, got {value!r}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"market value must be numeric or null, got {value!r}") from exc


def normalize_observation(raw: Mapping[str, Any]) -> StructuredObservation:
    """Create a structured observation without fabricating missing values."""
    if not isinstance(raw, Mapping):
        raise ValueError("raw observation must be a mapping")

    source_raw = raw.get("source") or {}
    instrument_raw = raw.get("instrument") or {}
    market_raw = raw.get("market_state") or {}

    if not isinstance(source_raw, Mapping):
        raise ValueError("source must be a mapping")
    if not isinstance(instrument_raw, Mapping):
        raise ValueError("instrument must be a mapping")
    if not isinstance(market_raw, Mapping):
        raise ValueError("market_state must be a mapping")

    market_state = {
        field_name: _number_or_none(market_raw.get(field_name))
        for field_name in MARKET_STATE_FIELDS
    }
    unknown = sorted(set(raw) - _TOP_LEVEL_FIELDS)
    supplied_unknown = raw.get("unknown_fields") or []
    if supplied_unknown:
        unknown.extend(str(field) for field in supplied_unknown)

    values = {
        "observed_at": str(raw.get("observed_at") or ""),
        "recorded_at": str(raw.get("recorded_at") or ""),
        "observer": str(raw.get("observer") or ""),
        "source": ObservationSource(
            platform=str(source_raw.get("platform") or ""),
            surface=str(source_raw.get("surface") or ""),
            account_context=str(source_raw.get("account_context") or ""),
        ),
        "instrument": ObservationInstrument(
            symbol=str(instrument_raw.get("symbol") or "").upper(),
            asset_class=(
                None
                if _blank_to_none(instrument_raw.get("asset_class")) is None
                else str(instrument_raw.get("asset_class")).lower()
            ),
        ),
        "market_state": market_state,
        "observation_type": str(raw.get("observation_type") or MANUAL_OBSERVATION_TYPE),
        "confidence": str(raw.get("confidence") or HUMAN_OBSERVED_CONFIDENCE),
        "unknown_fields": unknown,
        "notes": None if _blank_to_none(raw.get("notes")) is None else str(raw.get("notes")),
    }
    if raw.get("observation_id"):
        values["observation_id"] = str(raw["observation_id"])
    return StructuredObservation(**values)


def normalize_manual_envelope(envelope: Mapping[str, Any], *, recorded_at: str) -> StructuredObservation:
    """Normalize a SELFBULL-002 manual envelope into SELFBULL-003 memory form."""
    evidence = envelope.get("evidence") or {}
    if not isinstance(evidence, Mapping):
        evidence = {}
    instrument = envelope.get("instrument") or {}
    quote = envelope.get("quote") or {}
    if not isinstance(instrument, Mapping):
        instrument = {}
    if not isinstance(quote, Mapping):
        quote = {}
    return normalize_observation(
        {
            "observed_at": envelope.get("observed_at"),
            "recorded_at": recorded_at,
            "observer": "human",
            "source": {
                "platform": "webull",
                "surface": "browser",
                "account_context": "manual_view_only",
            },
            "instrument": {
                "symbol": instrument.get("symbol"),
                "asset_class": instrument.get("instrument_type"),
            },
            "market_state": quote,
            "observation_type": MANUAL_OBSERVATION_TYPE,
            "confidence": HUMAN_OBSERVED_CONFIDENCE,
            "unknown_fields": evidence.get("missing_fields") or [],
            "notes": evidence.get("operator_notes"),
        }
    )
