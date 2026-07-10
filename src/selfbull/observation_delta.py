"""SELFBULL-003 factual observation delta engine."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

FACTUAL_DELTA_TYPES = (
    "price_changed",
    "spread_widened",
    "volume_increased",
    "open_interest_changed",
    "field_became_available",
    "field_became_unavailable",
    "observation_conflict_detected",
)


@dataclass(frozen=True)
class ObservationDelta:
    delta_type: str
    field: str
    previous: Any
    current: Any

    def to_json_dict(self) -> Dict[str, Any]:
        return {
            "delta_type": self.delta_type,
            "field": self.field,
            "previous": self.previous,
            "current": self.current,
        }


def _state(record: Mapping[str, Any]) -> Mapping[str, Any]:
    state = record.get("market_state") or {}
    return state if isinstance(state, Mapping) else {}


def _add_availability_delta(
    deltas: List[ObservationDelta],
    *,
    field: str,
    previous: Any,
    current: Any,
) -> None:
    if previous is None and current is not None:
        deltas.append(ObservationDelta("field_became_available", field, previous, current))
    elif previous is not None and current is None:
        deltas.append(ObservationDelta("field_became_unavailable", field, previous, current))


def compare_observations(previous: Mapping[str, Any], current: Mapping[str, Any]) -> List[ObservationDelta]:
    """Compare observations using factual labels only."""
    prior = _state(previous)
    now = _state(current)
    deltas: List[ObservationDelta] = []

    for field in sorted(set(prior) | set(now)):
        _add_availability_delta(
            deltas,
            field=field,
            previous=prior.get(field),
            current=now.get(field),
        )

    if prior.get("last_price") is not None and now.get("last_price") is not None:
        if prior.get("last_price") != now.get("last_price"):
            deltas.append(ObservationDelta("price_changed", "last_price", prior.get("last_price"), now.get("last_price")))
    if prior.get("spread") is not None and now.get("spread") is not None:
        if now.get("spread") > prior.get("spread"):
            deltas.append(ObservationDelta("spread_widened", "spread", prior.get("spread"), now.get("spread")))
    if prior.get("volume") is not None and now.get("volume") is not None:
        if now.get("volume") > prior.get("volume"):
            deltas.append(ObservationDelta("volume_increased", "volume", prior.get("volume"), now.get("volume")))
    if prior.get("open_interest") is not None and now.get("open_interest") is not None:
        if prior.get("open_interest") != now.get("open_interest"):
            deltas.append(
                ObservationDelta(
                    "open_interest_changed",
                    "open_interest",
                    prior.get("open_interest"),
                    now.get("open_interest"),
                )
            )

    if current.get("validation_errors"):
        deltas.append(
            ObservationDelta(
                "observation_conflict_detected",
                "validation_errors",
                None,
                list(current.get("validation_errors") or []),
            )
        )

    return deltas


def delta_dicts(previous: Mapping[str, Any], current: Mapping[str, Any]) -> List[Dict[str, Any]]:
    return [delta.to_json_dict() for delta in compare_observations(previous, current)]
