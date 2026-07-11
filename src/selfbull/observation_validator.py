"""SELFBULL-003 structured observation validation."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping

from selfbull.observation_schema import (
    HUMAN_OBSERVED_CONFIDENCE,
    MANUAL_OBSERVATION_TYPE,
    MARKET_STATE_FIELDS,
    StructuredObservation,
)


@dataclass(frozen=True)
class ObservationValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)


def _as_dict(observation: Any) -> Dict[str, Any]:
    if isinstance(observation, StructuredObservation):
        return observation.to_json_dict()
    if isinstance(observation, Mapping):
        return dict(observation)
    raise ValueError("observation must be a StructuredObservation or mapping")


def validate_observation(observation: Any) -> ObservationValidationResult:
    errors: List[str] = []
    try:
        record = _as_dict(observation)
    except ValueError as exc:
        return ObservationValidationResult(valid=False, errors=[str(exc)])

    if record.get("execution_authority") is not False:
        errors.append("execution_authority must be false for observation evidence")

    for field_name in ("observation_id", "observed_at", "recorded_at", "observer"):
        if not record.get(field_name):
            errors.append(f"{field_name} is required")

    if record.get("observer") != "human":
        errors.append("observer must be human")
    if record.get("observation_type") != MANUAL_OBSERVATION_TYPE:
        errors.append(f"observation_type must be {MANUAL_OBSERVATION_TYPE!r}")
    if record.get("confidence") != HUMAN_OBSERVED_CONFIDENCE:
        errors.append(f"confidence must be {HUMAN_OBSERVED_CONFIDENCE!r}")

    source = record.get("source") or {}
    if not isinstance(source, Mapping):
        errors.append("source provenance is required")
        source = {}
    for field_name in ("platform", "surface", "account_context"):
        if not source.get(field_name):
            errors.append(f"source.{field_name} is required")
    if source.get("platform") != "webull":
        errors.append("source.platform must be webull")
    if source.get("surface") != "browser":
        errors.append("source.surface must be browser")
    if source.get("account_context") != "manual_view_only":
        errors.append("source.account_context must be manual_view_only")

    instrument = record.get("instrument") or {}
    if not isinstance(instrument, Mapping):
        errors.append("instrument is required")
        instrument = {}
    if not instrument.get("symbol"):
        errors.append("instrument.symbol is required")

    market_state = record.get("market_state") or {}
    if not isinstance(market_state, Mapping):
        errors.append("market_state is required")
        market_state = {}
    for field_name in MARKET_STATE_FIELDS:
        value = market_state.get(field_name)
        if value is not None and not isinstance(value, (int, float)):
            errors.append(f"market_state.{field_name} must be numeric or null")

    try:
        json.dumps(record, allow_nan=False)
    except (TypeError, ValueError) as exc:
        errors.append(f"observation must be JSON-serializable: {exc}")

    return ObservationValidationResult(valid=not errors, errors=errors)
