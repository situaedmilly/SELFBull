"""SELFBULL-003 retrospective replay utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from selfbull.observation_delta import delta_dicts
from selfbull.snapshot_ledger import SnapshotLedger


@dataclass(frozen=True)
class ReplayFrame:
    sequence: int
    entry_type: str
    observation_id: str
    observed_at: Optional[str]
    recorded_at: Optional[str]
    record: Dict[str, Any]
    deltas: List[Dict[str, Any]]

    def to_json_dict(self) -> Dict[str, Any]:
        return {
            "sequence": self.sequence,
            "entry_type": self.entry_type,
            "observation_id": self.observation_id,
            "observed_at": self.observed_at,
            "recorded_at": self.recorded_at,
            "record": self.record,
            "deltas": list(self.deltas),
        }


def replay_entries(entries: List[Dict[str, Any]]) -> List[ReplayFrame]:
    frames: List[ReplayFrame] = []
    prior_observation: Optional[Dict[str, Any]] = None
    for index, entry in enumerate(entries):
        entry_type = str(entry.get("entry_type", ""))
        deltas: List[Dict[str, Any]] = []
        if entry_type in {"observation", "revision"} and prior_observation is not None:
            deltas = delta_dicts(prior_observation, entry)
        frame = ReplayFrame(
            sequence=index,
            entry_type=entry_type,
            observation_id=str(entry.get("observation_id", "")),
            observed_at=entry.get("observed_at"),
            recorded_at=entry.get("recorded_at"),
            record=dict(entry),
            deltas=deltas,
        )
        frames.append(frame)
        if entry_type in {"observation", "revision"}:
            prior_observation = entry
    return frames


def replay_ledger(ledger: SnapshotLedger) -> List[Dict[str, Any]]:
    return [frame.to_json_dict() for frame in replay_entries(ledger.entries())]
