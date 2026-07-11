"""SELFBULL-003 append-only snapshot ledger."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from selfbull.observation_schema import StructuredObservation
from selfbull.observation_validator import validate_observation


class SnapshotLedgerError(ValueError):
    """Raised when the ledger refuses an unsafe evidence write."""


@dataclass(frozen=True)
class LedgerReceipt:
    ledger_index: int
    entry_type: str
    observation_id: str
    record_hash: str
    path: str

    def to_json_dict(self) -> Dict[str, Any]:
        return {
            "ledger_index": self.ledger_index,
            "entry_type": self.entry_type,
            "observation_id": self.observation_id,
            "record_hash": self.record_hash,
            "path": self.path,
        }


def canonical_json(record: Dict[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def record_hash(record: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()


def _ensure_json_safe(record: Dict[str, Any], *, error_message: str) -> None:
    try:
        json.dumps(record, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise SnapshotLedgerError(error_message) from exc


class SnapshotLedger:
    """Append-only JSONL ledger for structured observations and revisions."""

    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)

    def _read_entries(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        entries: List[Dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    entries.append(json.loads(line))
        return entries

    def entries(self) -> List[Dict[str, Any]]:
        return self._read_entries()

    def _append_entry(self, entry: Dict[str, Any]) -> LedgerReceipt:
        entries = self._read_entries()
        entry["ledger_index"] = len(entries)
        digest = record_hash(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(canonical_json(entry) + "\n")
        return LedgerReceipt(
            ledger_index=entry["ledger_index"],
            entry_type=str(entry.get("entry_type", "")),
            observation_id=str(entry.get("observation_id", "")),
            record_hash=digest,
            path=str(self.path),
        )

    def append_observation(self, observation: StructuredObservation) -> LedgerReceipt:
        validation = validate_observation(observation)
        if not validation.valid:
            raise SnapshotLedgerError("; ".join(validation.errors))
        record = observation.to_json_dict()
        record["entry_type"] = "observation"
        return self._append_entry(record)

    def append_revision(
        self,
        *,
        original_observation_id: str,
        corrected_observation: StructuredObservation,
        reason: str,
    ) -> LedgerReceipt:
        if not original_observation_id:
            raise SnapshotLedgerError("original_observation_id is required")
        if not reason:
            raise SnapshotLedgerError("revision reason is required")
        validation = validate_observation(corrected_observation)
        if not validation.valid:
            raise SnapshotLedgerError("; ".join(validation.errors))
        record = corrected_observation.to_json_dict()
        if record["observation_id"] == original_observation_id:
            raise SnapshotLedgerError("correction must create a new revision observation_id")
        record["entry_type"] = "revision"
        record["revision_of"] = original_observation_id
        record["revision_reason"] = reason
        return self._append_entry(record)

    def append_validation_failure(
        self,
        *,
        raw_observation: Dict[str, Any],
        errors: List[str],
        recorded_at: str,
    ) -> LedgerReceipt:
        entry = {
            "entry_type": "validation_failure",
            "observation_id": str(raw_observation.get("observation_id") or ""),
            "recorded_at": recorded_at,
            "raw_observation": raw_observation,
            "validation_errors": list(errors),
            "execution_authority": False,
        }
        _ensure_json_safe(entry, error_message="validation-failure evidence is not JSON serializable")
        return self._append_entry(entry)

    def find(self, observation_id: str) -> Optional[Dict[str, Any]]:
        for entry in self._read_entries():
            if entry.get("observation_id") == observation_id:
                return entry
        return None
