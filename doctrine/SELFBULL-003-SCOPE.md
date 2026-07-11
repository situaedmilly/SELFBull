# SELFBULL-003 Scope - Observation Alchemy

> Status: scope draft only. Authorized by
> `AUTHORIZE_SELFBULL_003_OBSERVATION_ALCHEMY_SCOPE_DRAFT_ONLY`.
> This document does not authorize implementation, Webull API access,
> browser automation, credential custody, live market-data connectivity,
> alerts, recommendations, paper trading, or execution.

## 0. Title

SELFBULL-003 - OBSERVATION ALCHEMY

Manual Intake -> Structured Evidence -> Replayable State

## 1. Prior sealed state

SELFBULL-001 established the quarantined broker-surface foundation:
offline, unauthenticated, non-networked, non-executing, and governed by
local contracts.

SELFBULL-002 established lawful manual browser observation intake:

```text
Human observes Webull browser
-> human records observation
-> SELFBull validates and normalizes the manual record
-> SELFBull stores accepted records as broker-neutral evidence
```
SELFBULL-002 created the mouth. SELFBULL-003 creates the memory organ.

## 2. Objective

SELFBULL-003 converts manually observed browser market facts into
governed, structured, replayable evidence without granting SELFBull
independent market access.

The system may answer:

- What was observed?
- When was it observed?
- By whom was it recorded?
- From which browser surface did it come?
- What changed since the prior observation?
- How confident is the record?
- What remains unknown?

The system must remain incapable of answering:

- Should I buy?
- Should I sell?
- What order should I place?
- What target, entry, exit, or prediction should be acted on?

## 3. Canonical flow

```text
Human Browser Observation
-> Manual Intake
-> Observation Normalizer
-> Evidence Validator
-> Snapshot Ledger
-> Delta Engine
-> Replay / Audit View
```

This is not `Browser -> Bot`.

This is:

```text
Browser -> Witness -> Evidence -> Memory
```

## 4. Recommended implementation artifacts

Implementation requires a separate authorization token. If authorized later,
the expected implementation surface is:

- `src/selfbull/observation_schema.py`
- `src/selfbull/observation_normalizer.py`
- `src/selfbull/observation_validator.py`
- `src/selfbull/snapshot_ledger.py`
- `src/selfbull/observation_delta.py`
- `src/selfbull/replay.py`
- `tests/test_observation_schema.py`
- `tests/test_observation_normalizer.py`
- `tests/test_snapshot_ledger.py`
- `tests/test_observation_delta.py`
- `tests/test_replay.py`

This scope draft creates none of those implementation files.

## 5. Canonical observation object

The SELFBULL-003 observation object should be JSON-serializable and should
carry provenance, missingness, confidence, and authority boundaries as data:

```json
{
  "observation_id": "selfbull-obs-...",
  "observed_at": "2026-07-10T18:30:00Z",
  "recorded_at": "2026-07-10T18:31:12Z",
  "observer": "human",
  "source": {
    "platform": "webull",
    "surface": "browser",
    "account_context": "manual_view_only"
  },
  "instrument": {
    "symbol": "SPY",
    "asset_class": "equity"
  },
  "market_state": {
    "last_price": null,
    "bid": null,
    "ask": null,
    "volume": null,
    "open_interest": null,
    "implied_volatility": null
  },
  "observation_type": "manual_snapshot",
  "confidence": "human_observed",
  "unknown_fields": [],
  "notes": null,
  "execution_authority": false
}
```

`execution_authority` must be hard-pinned false. Missing optional market
values must remain `null`. Unknown values must not be fabricated.

## 6. Hard invariants

These are code requirements for a later implementation, not prose-only
preferences:

- Manual Observation != Market Truth.
- Recorded Value != Live Feed.
- Historical Snapshot != Current State.
- Delta != Signal.
- Replay != Prediction.
- Evidence != Authority.
- `execution_authority` remains false and unrepresentable as true.
- Source provenance is mandatory.
- Timestamps are preserved exactly.
- Missing optional market values remain `null`.
- No inferred values are produced for missing fields.
- Prior observation records are not silently overwritten.
- Corrections create new revision records.
- The evidence ledger is append-only.
- Every validation failure remains replayable as audit evidence.

## 7. Required structural restrictions

SELFBULL-003 must not introduce:

- Webull API imports.
- Browser automation.
- Credential handling.
- Session cookies.
- Order endpoints.
- Background polling.
- Live quotes.
- Automated refresh.
- Portfolio import.
- Options chain ingestion.
- Order placement.
- Order cancellation.
- Paper trading.
- Recommendation logic.
- Alert logic.
- Autonomous judgment.

## 8. Delta engine scope

The delta engine may state factual changes only:

- `price_changed`
- `spread_widened`
- `volume_increased`
- `open_interest_changed`
- `field_became_available`
- `field_became_unavailable`
- `observation_conflict_detected`

The delta engine must not emit predictive or directive vocabulary,
including:

- `bullish`
- `bearish`
- `buy`
- `sell`
- `entry`
- `exit`
- `signal`
- `target`
- `prediction`

## 9. Replay scope

Replay reconstructs chronology for audit and research:

```text
Observation 001
-> Observation 002
-> Observation 003
```

Replay must show:

- exact observation timestamp,
- exact recorded fields,
- missing fields,
- revisions,
- deltas,
- provenance,
- validation failures.

Replay must not simulate trades, project outcomes, recommend action, or
convert historical evidence into live state.

## 10. Proof standard for implementation

SELFBULL-003 is not complete until a later implementation proves:

| Proof | Required result |
|---|---|
| Valid manual observation accepted | Pass |
| Missing required provenance rejected | Pass |
| Missing optional market values remain null | Pass |
| Unknown values are never fabricated | Pass |
| Prior records cannot be overwritten | Pass |
| Corrections create revisions | Pass |
| Delta engine reports factual changes only | Pass |
| Predictive vocabulary absent | Pass |
| Webull API imports absent | Pass |
| Execution authority remains unrepresentable | Pass |
| Replay reconstructs exact chronology | Pass |
| Tests, compile, clean tree | Pass |

## 11. Completion condition

SELFBULL-003 is complete only when a human can enter a browser-observed
market state and SELFBull can preserve it as immutable structured evidence,
compare it against previous observations, and replay the chronology without
adding prediction, automation, credential access, independent market access,
or execution capability.

## 12. Later gate sequence

The doctrine sequence remains:

```text
SELFBULL-001 - Establish governance.
SELFBULL-002 - Establish lawful human observation intake.
SELFBULL-003 - Transmute observation into durable evidence.
SELFBULL-004 - Derive factual state transitions.
SELFBULL-005 - Accumulate behavioral memory.
SELFBULL-006 - Introduce bounded judgment.
SELFBULL-007 - Authorize paper-only action.
SELFBULL-008 - Consider live authority under separate constitutional review.
```
