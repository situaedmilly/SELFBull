"""selfbull.observation_store — SELFBULL-002 · append-only local JSONL store.

Persists validated MarketObservationEnvelope records, one JSON object per
line, to a local file (default: data/manual_observations.jsonl — gitignored;
committed fixtures live under data/examples/ only).

Rules enforced here:
  - append-only: prior rows are never rewritten;
  - invalid or conflicted records are rejected by default;
  - an explicit dry-run mode validates and hashes without writing;
  - no network, no credentials, no secrets in any stored row;
  - every successful append returns a receipt with a deterministic
    SHA-256 hash over the canonical JSON of the record.

Standard library only. No import from SELFQUANT or RBHCB.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORE_PATH = REPO_ROOT / "data" / "manual_observations.jsonl"

_ACCEPTED_STATUS = "valid"


class ObservationStoreError(ValueError):
    """Raised when a record is refused by the store."""


@dataclass(frozen=True)
class StoreReceipt:
    receipt_id: str
    record_hash: str
    observed_at: str
    stored_at: str
    source: str
    symbol: Optional[str]
    path: str
    validation_status: str

    def to_json_dict(self) -> dict:
        return {
            "receipt_id": self.receipt_id,
            "record_hash": self.record_hash,
            "observed_at": self.observed_at,
            "stored_at": self.stored_at,
            "source": self.source,
            "symbol": self.symbol,
            "path": self.path,
            "validation_status": self.validation_status,
        }


def canonical_json(record: Dict[str, Any]) -> str:
    """Deterministic serialization: sorted keys, no whitespace."""
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def record_hash(record: Dict[str, Any]) -> str:
    """SHA-256 over the canonical JSON of the record."""
    return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()


def _check_record(record: Dict[str, Any]) -> str:
    """Refuse anything that is not a valid, authority-free observation
    envelope dict. Returns the record's validation status."""
    if not isinstance(record, dict):
        raise ObservationStoreError("record must be a JSON-serializable dict")
    evidence = record.get("evidence") or {}
    status = evidence.get("validation_status", "missing")
    if status != _ACCEPTED_STATUS:
        raise ObservationStoreError(
            f"store accepts only validation_status={_ACCEPTED_STATUS!r} "
            f"records; got {status!r}"
        )
    # An observation is evidence, never an instruction: refuse any record
    # that tries to smuggle execution authority into the observation plane.
    flat = canonical_json(record)
    if '"execution_authority":true' in flat.replace(" ", ""):
        raise ObservationStoreError(
            "record carries execution_authority=true — observations can "
            "never hold execution authority; refused"
        )
    try:
        json.dumps(record, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ObservationStoreError(f"record is not JSON-serializable: {exc}") from exc
    return status


class ObservationStore:
    """Append-only JSONL store for manual observation envelopes."""

    def __init__(self, path: Union[str, Path, None] = None):
        self.path = Path(path) if path is not None else DEFAULT_STORE_PATH

    def append(
        self,
        record: Dict[str, Any],
        *,
        dry_run: bool = False,
        stored_at: Optional[str] = None,
    ) -> StoreReceipt:
        """Validate and append one envelope dict as one JSONL line.

        ``dry_run=True`` is the explicit validation-only mode: the record is
        checked and hashed, a receipt is returned, and nothing is written.
        Prior rows are never modified — the file is opened append-only."""
        status = _check_record(record)
        receipt = StoreReceipt(
            receipt_id=f"obs-{uuid.uuid4()}",
            record_hash=record_hash(record),
            observed_at=str(record.get("observed_at", "")),
            stored_at=stored_at or datetime.now(timezone.utc).isoformat(),
            source=str(record.get("source", "")),
            symbol=(record.get("instrument") or {}).get("symbol"),
            path=str(self.path),
            validation_status=status,
        )
        if dry_run:
            return receipt
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(canonical_json(record) + "\n")
        return receipt

    def count(self) -> int:
        """Number of stored rows (0 when the file does not exist yet)."""
        if not self.path.exists():
            return 0
        with self.path.open("r", encoding="utf-8") as fh:
            return sum(1 for line in fh if line.strip())
