# SELFBull

**SELFBull is not a trading bot. SELFBull is a broker interface temple.**
The hand does not execute until the crown authorizes.

SELFBull is the quarantined, standalone Webull Open API broker-surface
adapter for the SELF ecosystem. It is a **hand**, not a **crown**: it
understands Webull's documented vocabulary and produces broker-neutral
facts and prepared order intents. It never decides whether an intent may
advance — that judgment belongs entirely to SELFQUANT's Agent Constitution
(`governed_decision()`), which this repository does not import, vendor, or
duplicate.

See `docs/SELFBULL-INTERFACE-CONTRACT.md` for the cross-repo JSON contract
and `docs/SELFBULL-PHASE1-SPEC.md` for exactly what Phase 1 does and does
not do.

## Phase 1, in one line

Offline. Unauthenticated. Non-networked. Non-executing. Independently
testable. Contract-driven. Standard-library only.

## Phase 1.1 — manual browser observation intake (SELFBULL-002)

SELFBull can now ingest **manually observed** Webull browser data into
validated, source-labeled, broker-neutral `MarketObservationEnvelope`
records (`source = webull_browser_manual`, capture mode
`MANUAL_BROWSER_OBSERVATION`), stored append-only in a local, gitignored
JSONL file. No live Webull API connection exists. No credential plane
exists. No execution authority exists. No trade is recommended or
transmitted.

```
python3 -m selfbull.manual_capture validate --file data/examples/manual_frequency_capture.csv
python3 -m selfbull.manual_capture ingest   --file my_capture.csv [--dry-run] [--json]
python3 -m selfbull.manual_capture single   --timestamp-et "2026-07-10 09:35:00" \
    --symbol SPY --last-price 632.14 --source webull_browser_manual
```

See `docs/SELFBULL-MANUAL-OBSERVATION-SPEC.md` (validation and envelope
rules) and `docs/SELFBULL-MOBILE-CAPTURE-GUIDE.md` (operator how-to).

## Boundary law

- SELFBull MUST NOT import SELFQUANT.
- SELFQUANT MUST NOT be vendored, copied, or included as a submodule here.
- SELFBull MUST NOT implement a second governor, Constitution,
  execution-authority engine, or gate ladder.
- SELFQUANT remains the sole authority plane. SELFBull is a broker-surface
  organ only.

## Running the tests

```
python3 -m unittest discover -s tests -v
```

No `pytest`, no third-party dependency, no network call — by construction.
