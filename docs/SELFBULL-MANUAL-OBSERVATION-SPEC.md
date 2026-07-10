# SELFBULL Manual Observation Specification — SELFBULL-002 (Phase 1.1)

> **Status:** sealed with SELFBULL-002. Defines the
> `MANUAL_BROWSER_OBSERVATION` intake mode: the operator reads the Webull
> **browser** interface with their own eyes and types the values by hand.
> No Webull API connection exists. No credential plane exists. No execution
> authority exists. No trade is recommended or transmitted.

## 0. What this mode is — and is not

```
Webull browser (human eyes)
  → manual structured capture (CSV or CLI arguments)
  → validation + normalization        (selfbull.observation_parser)
  → broker-neutral envelope           (MarketObservationEnvelope, contract v1.0)
  → append-only local JSONL store     (selfbull.observation_store)
  → future SELFQUANT frequency analysis (NOT in this repo, NOT in this phase)
```

This is **not** a workaround for missing OpenAPI credentials. It is a
deliberately separate ingestion mode that must remain distinguishable from
any future API-derived data forever:

| | Manual browser mode (this spec) | Future API mode (not built) |
|---|---|---|
| `source` | `webull_browser_manual` | a *different* identifier, never this one |
| `evidence.capture_mode` | `MANUAL_BROWSER_OBSERVATION` | its own mode name |
| network | none, structurally | separately authorized phase |
| credentials | none read, none stored | separately authorized phase |

The intake layer only **captures → validates → normalizes → serializes →
preserves evidence**. It never predicts, ranks trades, recommends options,
authorizes execution, or submits orders. No observation is ever upgraded
into certainty: contradictions, missing fields, and raw input are preserved
verbatim in the evidence block.

## 1. Input record

Required fields:

| Field | Meaning |
|---|---|
| `timestamp_et` | when the operator observed the browser, US Eastern wall clock |
| `symbol` | instrument symbol as displayed |
| `last_price` | last traded price as displayed |
| `source` | must be exactly `webull_browser_manual` |

Optional fields (missing values are `null` — never `0`, `n/a`, or
`unknown` unless literally observed):

`day_open`, `day_high`, `day_low`, `previous_close`, `volume`,
`relative_volume`, `bid`, `ask`, `spread`, `implied_volatility`,
`expected_move`, `call_wall`, `put_wall`, `largest_call_volume_strike`,
`largest_put_volume_strike`, `session`, `notes`.

The committed example file (`data/examples/manual_frequency_capture.csv`)
uses the current observation universe `SPY / QQQ / IWM / DIA / VIX`. That
universe is a convention of the example file, **not** a hard-coded validator
rule — any symbol passing the safety pattern below is accepted.

## 2. Validation rules

**Timestamp** — parsed as ISO-8601 or `YYYY-MM-DD HH:MM:SS`; a naive stamp
is interpreted as US Eastern (IANA `America/New_York`, with a built-in
post-2007 DST fallback when the host lacks tzdata); normalized to ISO-8601
with timezone offset (e.g. `2026-07-09T09:35:00-04:00`). Impossible stamps
and stamps more than 5 minutes in the future are rejected. A missing
timestamp is **never** silently replaced with "now".

**Symbol** — trimmed, uppercased, must match `^[A-Z0-9.\-^]{1,12}$`
(index-like symbols such as `VIX` or `^VIX` pass). Empty or unsafe symbols
are rejected.

**Numerics** — integer, float, or decimal string accepted; blank means
missing (`null`). `NaN`, infinity, and malformed strings are rejected.
Price-like fields (`last_price`, `day_open/high/low`, `previous_close`,
walls, strikes) must be strictly positive; `bid`, `ask`, `spread`,
`volume`, `relative_volume`, `implied_volatility`, `expected_move` must be
non-negative (zero is semantically valid there).

**Spread** — never fabricated. If `bid` and `ask` are both present and no
spread was supplied, `spread = ask - bid` is derived. If a supplied spread
differs from the calculated one by more than one cent, the supplied value
is **preserved**, the record is marked `conflicted`, and the contradiction
is recorded in `evidence.validation_errors`. Operator evidence is never
silently overwritten.

**Market consistency** — when present: `day_low ≤ last_price ≤ day_high`,
`day_low ≤ day_open ≤ day_high`, `day_low ≤ day_high`. Violations mark the
record `conflicted` with an explicit error message.

**Source** — must be exactly `webull_browser_manual`; anything else is
invalid in this mode.

### Validation statuses

| Status | Meaning | Stored? |
|---|---|---|
| `valid` | every check passed | yes |
| `conflicted` | internally contradictory operator evidence (spread vs bid/ask, price outside range); values preserved | no (refused by store by default) |
| `invalid` | required field missing/unparseable, malformed value, wrong source | no |

## 3. Output envelope

Each accepted record becomes a `MarketObservationEnvelope`
(`selfbull.contracts`, schema `1.0` — the sealed interface contract in
`docs/SELFBULL-INTERFACE-CONTRACT.md` is the source of truth):

| Field | Value in this mode |
|---|---|
| `schema_version` | `"1.0"` |
| `broker` | `"webull"` |
| `observed_at` | normalized ET ISO-8601 stamp with offset |
| `instrument` | `{"symbol": ..., "instrument_type": null}` — type is never inferred |
| `quote` | the normalized numeric fields (missing → `null`) |
| `session` | normalized lowercase session label or `null` |
| `source` | `"webull_browser_manual"` |
| `freshness` | the observation stamp (manual capture has no fetch age) |
| `evidence` | see below |

`evidence` always contains: `capture_mode` (`MANUAL_BROWSER_OBSERVATION`),
`raw_input` (operator's input, stringified, verbatim), `validation_status`,
`validation_errors`, `validation_warnings`, `missing_fields`,
`operator_notes`, and `network_call: false`.

The envelope is JSON-serializable with standard-library types only, and no
execution-authority field exists on it — an observation is evidence, never
an instruction. The store additionally refuses any record carrying
`execution_authority: true` anywhere in its body.

## 4. Storage

`selfbull.observation_store.ObservationStore` appends one canonical-JSON
object per line to `data/manual_observations.jsonl` (gitignored; only
`data/examples/` fixtures are committed). Rules: append-only (prior rows
never rewritten), parent directory auto-created, invalid/conflicted records
refused, explicit dry-run mode writes nothing, no secrets, no network.

Every successful append returns a receipt:
`receipt_id`, `record_hash` (SHA-256 over canonical JSON — sorted keys, no
whitespace — deterministic per record), `observed_at`, `stored_at`,
`source`, `symbol`, `path`, `validation_status`.

## 5. Frequency-analysis readiness (captured, not interpreted)

The preserved fields are sufficient for SELFQUANT to later derive range
expansion/compression, price velocity, volume acceleration, spread
expansion/contraction, magnet persistence/migration, strike interaction,
session transition, freshness, and field contradiction. **None of these
analytics are implemented in this repo or this phase.** This pass captures
matter; it does not interpret the field.

## 6. Language law (what may truthfully be claimed)

SELFBull can now ingest manually observed Webull browser data into
validated, source-labeled, broker-neutral observation envelopes.
No live Webull API connection exists. No credential plane exists. No
execution authority exists. No trade is recommended or transmitted.
