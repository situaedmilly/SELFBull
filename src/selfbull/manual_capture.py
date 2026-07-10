"""selfbull.manual_capture — SELFBULL-002 · mobile-first manual intake CLI.

Converts manually observed Webull *browser* readings (typed by the operator)
into validated, source-labeled, broker-neutral MarketObservationEnvelope
records. Capture mode: MANUAL_BROWSER_OBSERVATION.

    python3 -m selfbull.manual_capture validate --file data/examples/manual_frequency_capture.csv
    python3 -m selfbull.manual_capture ingest   --file capture.csv [--dry-run] [--json]
    python3 -m selfbull.manual_capture single   --timestamp-et "2026-07-10 09:35:00" \
        --symbol SPY --last-price 632.14 --source webull_browser_manual

No network call, no authentication, no broker connectivity, no order path,
no trade recommendation exists anywhere in this module. Exit status is
non-zero when any record fails validation. Standard library only, and no
import of SELFQUANT or RBHCB code.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from selfbull.observation_parser import (
    ALL_FIELDS,
    MANUAL_SOURCE,
    OPTIONAL_FIELDS,
    ParsedObservation,
    build_envelope,
    parse_observation,
)
from selfbull.observation_store import ObservationStore

EXIT_OK = 0
EXIT_VALIDATION_FAILED = 1
EXIT_USAGE = 2


def read_csv_rows(path: Path) -> List[Dict[str, Any]]:
    """Read a manual-capture CSV into raw row dicts. Blank cells stay as
    empty strings for the parser to normalize to None."""
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return []
        return [dict(row) for row in reader]


def process_rows(
    rows: List[Dict[str, Any]],
    *,
    store: Optional[ObservationStore] = None,
    dry_run: bool = False,
) -> Tuple[List[Dict[str, Any]], int]:
    """Parse every row; append valid envelopes when a store is given.

    Nothing is written unless every row in the batch is valid — a batch with
    any invalid row writes zero rows, so a bad CSV never half-ingests.
    Returns (per-row results, exit_code)."""
    results: List[Dict[str, Any]] = []
    parsed_rows: List[Tuple[ParsedObservation, Dict[str, Any]]] = []
    all_valid = True

    for index, raw in enumerate(rows, start=1):
        parsed = parse_observation(raw)
        envelope = build_envelope(parsed).to_json_dict()
        entry: Dict[str, Any] = {
            "row": index,
            "symbol": parsed.normalized.get("symbol"),
            "observed_at": parsed.normalized.get("timestamp_et"),
            "validation_status": parsed.validation_status,
            "errors": parsed.errors,
            "warnings": parsed.warnings,
            "missing_fields": parsed.missing_fields,
        }
        if not parsed.is_valid:
            all_valid = False
        parsed_rows.append((parsed, envelope))
        results.append(entry)

    if store is not None and all_valid:
        for entry, (parsed, envelope) in zip(results, parsed_rows):
            receipt = store.append(envelope, dry_run=dry_run)
            entry["receipt"] = receipt.to_json_dict()
            entry["written"] = not dry_run

    exit_code = EXIT_OK if all_valid else EXIT_VALIDATION_FAILED
    return results, exit_code


def _print_results(results: List[Dict[str, Any]], *, as_json: bool, header: str) -> None:
    if as_json:
        print(json.dumps({"mode": header, "results": results}, indent=2))
        return
    print(f"[selfbull] {header}: {len(results)} record(s)")
    for entry in results:
        status = entry["validation_status"]
        symbol = entry.get("symbol") or "?"
        stamp = entry.get("observed_at") or "?"
        line = f"  row {entry['row']:>3}  {symbol:<6} {stamp}  -> {status}"
        if entry.get("receipt"):
            verb = "would store (dry-run)" if not entry.get("written") else "stored"
            line += f"  [{verb} {entry['receipt']['record_hash'][:12]}…]"
        print(line)
        for err in entry["errors"]:
            print(f"        error: {err}")
        for warn in entry["warnings"]:
            print(f"        warning: {warn}")
    valid = sum(1 for e in results if e["validation_status"] == "valid")
    print(f"[selfbull] valid: {valid}/{len(results)}")


def _row_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    row: Dict[str, Any] = {}
    for name in ALL_FIELDS:
        value = getattr(args, name, None)
        if value is not None:
            row[name] = value
    return row


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m selfbull.manual_capture",
        description=(
            "SELFBull manual browser-observation intake "
            "(MANUAL_BROWSER_OBSERVATION). Offline: no network, no "
            "credentials, no orders."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common: List[Tuple[str, Dict[str, Any]]] = [
        ("--json", {"action": "store_true", "help": "emit machine-readable JSON results"}),
    ]

    p_validate = sub.add_parser("validate", help="validate a CSV file; write nothing")
    p_validate.add_argument("--file", required=True, help="path to a manual-capture CSV")
    for flag, kw in common:
        p_validate.add_argument(flag, **kw)

    p_ingest = sub.add_parser("ingest", help="validate a CSV file and append valid rows to the JSONL store")
    p_ingest.add_argument("--file", required=True, help="path to a manual-capture CSV")
    p_ingest.add_argument("--store-path", default=None, help="override JSONL store path (default: data/manual_observations.jsonl)")
    p_ingest.add_argument("--dry-run", action="store_true", help="validate and build receipts without writing")
    for flag, kw in common:
        p_ingest.add_argument(flag, **kw)

    p_single = sub.add_parser("single", help="validate/ingest one record from explicit arguments")
    p_single.add_argument("--timestamp-et", dest="timestamp_et", required=True)
    p_single.add_argument("--symbol", required=True)
    p_single.add_argument("--last-price", dest="last_price", required=True)
    p_single.add_argument("--source", required=True, help=f"must be {MANUAL_SOURCE!r}")
    for name in OPTIONAL_FIELDS:
        p_single.add_argument(f"--{name.replace('_', '-')}", dest=name, default=None)
    p_single.add_argument("--store-path", default=None, help="override JSONL store path")
    p_single.add_argument("--dry-run", action="store_true", help="validate without writing")
    p_single.add_argument("--validate-only", action="store_true", help="validate only; skip the store entirely")
    for flag, kw in common:
        p_single.add_argument(flag, **kw)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.command in ("validate", "ingest"):
        path = Path(args.file)
        if not path.exists():
            print(f"[selfbull] file not found: {path}", file=sys.stderr)
            return EXIT_USAGE
        rows = read_csv_rows(path)
        if not rows:
            print(f"[selfbull] no data rows found in {path}", file=sys.stderr)
            return EXIT_USAGE

    if args.command == "validate":
        results, code = process_rows(rows)
        _print_results(results, as_json=args.json, header="validate (no writes)")
        return code

    if args.command == "ingest":
        store = ObservationStore(args.store_path)
        results, code = process_rows(rows, store=store, dry_run=args.dry_run)
        header = "ingest (dry-run, no writes)" if args.dry_run else "ingest"
        _print_results(results, as_json=args.json, header=header)
        return code

    if args.command == "single":
        row = _row_from_args(args)
        store = None if args.validate_only else ObservationStore(args.store_path)
        results, code = process_rows([row], store=store, dry_run=args.dry_run)
        header = "single (validate-only)" if args.validate_only else (
            "single (dry-run, no writes)" if args.dry_run else "single"
        )
        _print_results(results, as_json=args.json, header=header)
        return code

    parser.error(f"unknown command {args.command!r}")
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
