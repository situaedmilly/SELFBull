# SELFBULL-004 Scope - Authenticated Market Observation Admission

> Status: doctrine draft for SELFBULL-004A only.
> Authorized surface: custody boundary, witness law, normalization law,
> and future subphase boundaries. This document does not authorize CLI
> login, MCP invocation, SDK authentication, broker requests, fixture
> admission, or transport implementation.

## 0. Title

SELFBULL-004 - AUTHENTICATED MARKET OBSERVATION ADMISSION

Custody -> Witness -> Normalization -> Transport -> Parity

## 1. Prior sealed state

SELFBULL-001 established the quarantined broker-surface foundation:
offline, unauthenticated, non-networked, non-executing.

SELFBULL-002 established lawful manual browser observation intake:

```text
Human browser observation
-> manual validation
-> normalized envelope
-> append-only local store
```

SELFBULL-003 established replayable structured evidence:

```text
Manual intake
-> structured observation
-> append-only ledger
-> factual deltas
-> replay
```

SELFBULL-004 introduces authenticated broker-reported market observation
without collapsing custody, witness, transport, and parity into one step.

## 2. Objective

SELFBULL-004 defines how authenticated Webull market-data observations may
eventually enter the same governed evidence system while preserving four
separate authority transitions:

- custody of credentials,
- witness capture,
- canonical SDK transport,
- cross-plane parity admission.

The system may answer:

- Which credential boundary is authorized?
- Which witness plane produced this observation?
- Which fields were actually observed?
- Which transport emitted the normalized record?
- Whether SDK output matches prior witnessed CLI/MCP evidence under an
  explicit parity policy.

The system must remain incapable of answering:

- Should I buy or sell?
- Which trade should be placed?
- Whether broker access alone grants canonical admission.
- Whether a successful SDK call implies parity has passed.

## 3. The four sealed subphases

### 004A - Custody and Witness Contract

Purpose:

- define doctrine,
- define credential law,
- define raw witness admission law,
- define normalization law,
- define CLI / MCP / SDK / parity boundaries.

Network authority:

- none.

### 004B - Read-Only Witness Capture

Purpose:

- perform human-run CLI market-data witness calls,
- perform bounded MCP market-data witness calls,
- capture ephemeral raw outputs,
- scrub and review derivatives before fixture admission.

Network authority:

- explicit human-run read-only broker calls only.

### 004C - Canonical SDK Transport

Purpose:

- implement the direct SDK market-data adapter with exactly two bounded
  public methods:
  - `get_stock_snapshot(symbol)`
  - `get_stock_bars(symbol, timespan, count)`

Network authority:

- two bounded read-only SDK calls only.

### 004D - Cross-Plane Parity Admission

Purpose:

- compare normalized CLI / MCP / SDK evidence,
- classify mismatches,
- decide whether SDK transport is admissible as canonical.

Network authority:

- none required if witness fixtures already exist.

## 4. Credential law

Credentials exist only in:

- runtime process environment, or
- an explicitly approved local credential store outside Git custody.

No credential may enter:

- source,
- Git history,
- fixtures,
- docs,
- tests,
- logs,
- exceptions,
- screenshots,
- shell transcripts,
- pull-request bodies,
- exported manifests,
- Google Drive manifests.

The application may report only presence / missing state.
Masked previews remain prohibited in SELFBULL-004A unless a later phase
explicitly authorizes a more specific redacted receipt shape.

## 5. Raw witness law

Raw CLI / MCP / SDK output is ephemeral and non-committable by default.

Required admission pipeline:

```text
capture
-> secret scan
-> identity scan
-> unstable-field classification
-> scrubbed derivative
-> human review
-> SHA-256 registration
-> fixture admission
```

Until that pipeline completes, a raw witness artifact is not a test
fixture and is not committed.

## 6. Normalization law

SELFBULL-004 preserves observed facts only.

Rules:

- missing values remain `null`,
- no confidence score is introduced,
- no recommendation or interpretation is introduced,
- no execution permission is introduced,
- local capture time does not replace market observation time.

SELFBULL-004 separates:

- `MarketObservation`
- `TransportReceipt`
- `RawWitnessReference`

These are distinct artifacts, not one merged object.

## 7. CLI law

The Webull CLI is human-operated diagnostic and witness infrastructure
only.

Allowed role:

- authentication witness,
- doctor output,
- deterministic read-only probes,
- independent comparison against SELFBULL normalization.

Forbidden role:

- application transport,
- subprocess dependency inside SELFBULL code,
- agent runtime with unrestricted command surface.

No SELFBULL application code may shell out to the Webull CLI.

## 8. MCP law

Local MCP is an agent observation plane only.

Initial admitted toolset:

- `market-data` only.

Not admitted in 004A:

- account tools,
- trading tools,
- broad toolset exposure,
- fixture admission without scrubbing and review.

## 9. SDK law

The Python SDK is the future canonical SELFBULL application transport.

Not authorized in 004A:

- SDK authentication,
- SDK network calls,
- generic endpoint dispatch,
- account client exposure,
- trading client exposure,
- token object exposure.

Future 004C public surface is limited to:

- `get_stock_snapshot(symbol)`
- `get_stock_bars(symbol, timespan, count)`

No generic dispatcher may be introduced.

## 10. Parity law

Cross-plane parity is a later, separate admission gate. It is not implied
by successful witness capture and is not implied by successful SDK access.

Mismatch classes must include:

- `exact_match`
- `timestamp_format_only`
- `null_vs_missing`
- `numeric_tolerance_match`
- `semantic_mismatch`
- `entitlement_mismatch`
- `unsupported_field`

Every parity report must record capture-time distance between planes.

## 11. Required implementation boundaries by subphase

004A may create doctrine and runbooks only.

004B may create reviewed scrubbed fixture derivatives only after the raw
witness pipeline completes.

004C may implement the bounded SDK adapter only after 004B witness shapes
exist.

004D may admit SDK transport as canonical only after explicit parity review.

## 12. Hard invariants

- Evidence != authority.
- Authentication != admission.
- Witness capture != fixture admission.
- SDK success != canonical trust.
- Missing != fabricated.
- Provenance != confidence.
- Raw witness != committable artifact.
- `execution_authority` remains structurally false.

## 13. Stop condition for 004A

Stop after:

- doctrine and runbooks are written,
- credential and witness boundaries are sealed,
- normalization contract is drafted,
- no broker request has been made,
- no live fixture has been created.
