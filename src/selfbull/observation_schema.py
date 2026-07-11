"""SELFBULL-003 structured observation evidence schema.

Manual browser observations become replayable evidence records. This module
contains no network client, no broker transport, no credential handling, and
no execution authority.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

OBSERVATION_SCHEMA_VERSION = "003.0"
MANUAL_OBSERVATION_TYPE = "manual_snapshot"
HUMAN_OBSERVED_CONFIDENCE = "human_observed"

MARKET_STATE_FIELDS = (
    "last_price",
    "bid",
    "ask",
    "spread",
    "volume",
    "open_interest",
    "implied_volatility",
)


def new_observation_id() -> str:
    return f"selfbull-obs-{uuid.uuid4()}"


@dataclass(frozen=True)
class ObservationSource:
    platform: str
    surface: str
    account_context: str

    def to_json_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "surface": self.surface,
            "account_context": self.account_context,
        }


@dataclass(frozen=True)
class ObservationInstrument:
    symbol: str
    asset_class: Optional[str]

    def to_json_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "asset_class": self.asset_class,
        }


@dataclass(frozen=True)
class StructuredObservation:
    observed_at: str
    recorded_at: str
    observer: str
    source: ObservationSource
    instrument: ObservationInstrument
    market_state: Dict[str, Optional[float]]
    observation_id: str = field(default_factory=new_observation_id)
    observation_type: str = MANUAL_OBSERVATION_TYPE
    confidence: str = HUMAN_OBSERVED_CONFIDENCE
    unknown_fields: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    schema_version: str = OBSERVATION_SCHEMA_VERSION
    execution_authority: bool = field(default=False, init=False)

    def to_json_dict(self) -> Dict[str, Any]:
        state = {field_name: self.market_state.get(field_name) for field_name in MARKET_STATE_FIELDS}
        return {
            "schema_version": self.schema_version,
            "observation_id": self.observation_id,
            "observed_at": self.observed_at,
            "recorded_at": self.recorded_at,
            "observer": self.observer,
            "source": self.source.to_json_dict(),
            "instrument": self.instrument.to_json_dict(),
            "market_state": state,
            "observation_type": self.observation_type,
            "confidence": self.confidence,
            "unknown_fields": list(self.unknown_fields),
            "notes": self.notes,
            "execution_authority": self.execution_authority,
        }
