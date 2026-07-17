# SELFBULL-004 Scope - Governed Read-Only Connectivity Admission

> Status: bootstrap-boundary correction for SELFBULL-004B-1 only.
> Authorized surface: environment, bootstrap, custody, token,
> configuration-retrieval, and future read-only data boundaries. This
> document does not authorize SDK import, SDK client construction,
> authentication, broker requests, fixture admission, or transport
> implementation.

## 0. Title

SELFBULL-004 - GOVERNED READ-ONLY CONNECTIVITY ADMISSION

Environment -> Token-Custody Preflight -> Bootstrap -> Market Data -> Account Observation

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

SELFBULL-004 introduces governed broker-reported observation without
collapsing environment readiness, SDK bootstrap, market-data transport,
account observation, and parity into one step.

## 2. Objective

SELFBULL-004 defines how Webull observations may eventually enter the same
governed evidence system while preserving separate authority transitions:

- environment readiness,
- potentially networked and token-active SDK bootstrap,
- market-data read,
- account-observation read,
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

## 3. The five operational gates

Each gate requires separate human authorization and independent review.
Advancement requires an explicit `PASS` verdict for the prior gate plus a
new human authorization for the next gate. Failure, an indeterminate
result, missing evidence, or absence of an explicit `PASS` produces
`HOLD`. Passing one gate does not authorize the next.

### Gate A - Environment Readiness

Gate A may prove only:

- an approved Python interpreter exists,
- a repository-local virtual environment exists,
- the approved SDK version is installed,
- SDK package metadata is readable,
- approved credential variable names are defined,
- required credential presence may be reported as `present` or `missing`,
- the non-secret region value may be checked,
- the STOP control may be checked.

Gate A may not:

- import Webull runtime modules when import side effects are unproven,
- construct any Webull client,
- create or refresh tokens,
- access token storage,
- contact Webull,
- read market data,
- read account data.

### Gate A2 - Token-Custody Preflight

Gate A2 may proceed only after Gate A receives an explicit `PASS` and a
separate human authorization is issued.

Gate A2 is a bounded subgate between environment readiness and live
bootstrap. It governs metadata-only custody inspection and configuration
required to prepare Gate B; it does not itself authorize bootstrap.

This section is the sole and authoritative definition of Gate A2's
inspection scope, `PASS` conditions, and `HOLD` conditions.
`docs/SELFBULL-004-CREDENTIAL-CUSTODY.md` applies this same boundary to
token custody specifically and must not restate it independently.

Gate A2 may inspect only:

- the SDK default token-storage directory,
- the intended/approved token-storage path,
- whether that path exists,
- parent-directory existence,
- path containment outside the repository (the exact approved absolute
  storage location resolves outside the repository),
- symlink status,
- filesystem ownership,
- filesystem permission mode,
- whether redirection/configuration is available,
- whether the target is writable,
- whether an empty custody directory can be safely prepared if separately
  allowed by this doctrine,
- whether a cleanup and revocation procedure exists before construction.

Gate A2 may not:

- read token file contents,
- print token values,
- parse token payloads,
- hash token values,
- authenticate,
- construct `ApiClient`,
- construct `DataClient`,
- construct `TradeClient`,
- retrieve remote configuration,
- call Webull,
- create or refresh a token,
- inspect account or market data.

Gate A2 `PASS` requires:

- an approved external storage location established,
- that location outside the repository,
- no unsafe symlink,
- acceptable, restrictive ownership and permissions,
- token contents not accessed,
- a configuration path established where supported,
- bounded expiration and refresh behavior sufficient for the witness,
- a cleanup and revocation procedure that exists before construction,
- all unknowns resolved sufficiently for Gate B.

Gate A2 `HOLD` applies when:

- the custody path remains unknown,
- the path is inside the repository,
- the path or parent resolves through an unsafe symlink,
- filesystem ownership is not restricted to the approved runtime identity,
- permissions are broader than doctrine permits,
- redirection requirements remain unresolved,
- expiration/refresh bounds, cleanup, or revocation cannot be established,
- token-value access would be required,
- evidence is incomplete.

On `HOLD`, no client may be constructed and Gate B may not be authorized.

Gate A2 preflight execution itself is not authorized by this doctrine-only
correction; only its authority boundary is defined here.

### Gate B - Bootstrap Witness

Gate B may proceed only after Gate A2 receives an explicit `PASS` and a
separate human authorization is issued. Its exact bootstrap sequence is:

1. construct `webull.core.client.ApiClient(app_key, app_secret, region_id)`
   from the approved runtime custody boundary,
2. construct `webull.data.data_client.DataClient(api_client)` exactly once.

The `DataClient` construction is the single governed initializer event.
Gate B may invoke no `DataClient` business-data method and may not construct
`TradeClient` or any other SDK client. Bootstrap is classified as
potentially networked and token-active, not as inert local initialization.

The witness may capture only:

- bootstrap attempted,
- bootstrap succeeded or failed,
- region,
- environment classification,
- SDK version,
- network boundary crossed: `yes`, `no`, or `unknown`,
- token storage touched (including the approved external location or any
  unexpected token path): `yes`, `no`, or `unknown`,
- configuration retrieval observed: `yes`, `no`, or `unknown`,
- expiration/refresh behavior observed within pre-authorized bounds:
  `yes`, `no`, or `unknown`,
- cleanup and revocation status: `completed`, `remaining-required`, or
  `not-applicable`,
- redacted error class if bootstrap failed.

For the network-boundary-crossed field: `yes` means direct evidence proves
the network boundary was crossed; `no` means direct evidence proves no
network boundary was crossed; `unknown` means instrumentation, early
failure, or incomplete evidence prevents a truthful determination. The same
tri-state rule governs any equivalent bootstrap evidence field, including
token storage touched and configuration retrieval observed, whenever direct
evidence may be unavailable.

- `unknown` must never be coerced to `no`.
- Network-capable must not be recorded as network-crossed.
- Bootstrap success must not automatically imply `yes`.
- Bootstrap failure must not automatically imply `no`.
- Receipt language must distinguish capability from witnessed behavior.

The witness must not capture credential values, token values, raw headers,
raw configuration that may contain secrets, account data, or market data.

### Gate C - Market-Data Read

Gate C may proceed only after Gate B receives an explicit independent
`PASS` and a separate human authorization. It may perform one bounded
read-only market-data request. It grants no polling, streaming,
subscription, account access, or retry beyond one explicitly bounded
transport attempt.

### Gate D - Account-Observation Read

Gate D may proceed only after Gate C receives an explicit independent
`PASS` and a separate future human authorization. It may include only
explicitly allowlisted read-only account endpoints and remains distinct
from market-data authority.

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

The approved SELFBull runtime variable names are:

- `SELFBULL_WEBULL_APP_KEY_ID`
- `SELFBULL_WEBULL_APP_KEY_SECRET`
- `SELFBULL_WEBULL_REGION_ID`
- `SELFBULL_STOP`

Credential state may be reported only as `present` or `missing`. Full,
partial, masked, first-character, last-character, and hashed credential
representations are prohibited. Any existing four-character App Key ID
preview is noncompliant with SELFBULL-004 custody law and requires a later
bounded implementation repair. This doctrine-only pass does not modify it.

The upstream SDK fallback names `WEBULL_APP_KEY_ID` and
`WEBULL_APP_KEY_SECRET` are compatibility facts, not the preferred
SELFBull interface. The non-secret region value may be reported directly.

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

- separately governed credential/bootstrap witness,
- doctor output,
- deterministic read-only probes,
- independent comparison against SELFBULL normalization.

Any CLI market-data probe requires Gate C authority. CLI availability or
credential acceptance does not satisfy Gate B and does not authorize a
market-data request.

Forbidden role:

- application transport,
- subprocess dependency inside SELFBULL code,
- agent runtime with unrestricted command surface.

No SELFBULL application code may shell out to the Webull CLI.

## 8. MCP law

Local MCP is an agent observation plane only.

Initial admitted toolset:

- `market-data` only.

The toolset allowlist does not itself authorize invocation. Any MCP
market-data probe requires Gate C authority after Gate B review.

Not authorized by this correction pass:

- account tools,
- trading tools,
- broad toolset exposure,
- fixture admission without scrubbing and review.

## 9. SDK law

The Python SDK is the future canonical SELFBULL application transport.

Not authorized by this correction pass:

- SDK authentication,
- SDK network calls,
- SDK runtime import,
- SDK client construction,
- generic endpoint dispatch,
- account client exposure,
- trading client exposure,
- token object exposure.

The public bootstrap prerequisite is
`webull.core.client.ApiClient(app_key, app_secret, region_id)`. The single
governed initializer event is exactly one construction of
`webull.data.data_client.DataClient(api_client)`. The SDK's
`AppKeyCredential` is an internal credential object. `region_id` is
required; the US region value is `us`. No business-data method may be
called during Gate B.

Construction of `DataClient` or `TradeClient` invokes
`ClientInitializer`. Initialization may retrieve remote configuration and
initialize token storage before a business-data method is called.
Therefore client construction is not inert local setup: it is classified
as a potentially networked and token-active bootstrap event requiring
Gate B authorization. Network denial or remote-configuration failure must
produce `HOLD`; silent fallback is prohibited.

The official quote call requires at least `symbol` and `category`. The
current SELFBull quote contract does not yet represent `category`. This is
a required future transport-contract reconciliation, not authority to
redesign the implementation contract in this pass.

TradeClient existence upstream grants no authority to instantiate or
expose it. SELFBull admits no order client, order methods, paper trading,
trade abstraction, execution route, mutation authority, or SELFQUANT
authority transfer.

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

## 11. Required implementation boundaries by gate

004B-1 may correct bootstrap doctrine only.

004B-2 may perform one controlled Gate B bootstrap witness only after Gate
A2 receives an explicit `PASS` and the corrected doctrine is independently
reviewed and sealed.

Gate C implementation and market-data observation remain unauthorized
until the bootstrap witness receives an explicit independent `PASS` and a
separate human authorization.

Gate D account-observation implementation requires an explicit Gate C
`PASS` and a separate future human authorization.

Cross-plane parity may admit SDK transport as canonical only after explicit
parity review.

## 12. Hard invariants

- Evidence != authority.
- Authentication != admission.
- Environment readiness != bootstrap success.
- SDK import != environment readiness when import side effects are unproven.
- Token-custody preflight PASS != bootstrap authorization.
- Client construction != inert local initialization.
- Network-capable != network-crossed.
- Bootstrap outcome != crossing determination.
- Bootstrap success != market-data authority.
- Market-data authority != account-observation authority.
- Witness capture != fixture admission.
- SDK success != canonical trust.
- Missing != fabricated.
- Provenance != confidence.
- Raw witness != committable artifact.
- `execution_authority` remains structurally false.

## 13. Gate verdicts and operational status

Until directly witnessed in the appropriate future gate, do not describe
SELFBull as authenticated, connected, ready for quotes, broker connected,
or token established.

Two vocabularies are kept explicitly separate and must never be conflated.

### Gate verdicts

- `PASS`
- `HOLD`
- `FAILED`

Gate verdicts govern whether advancement to the next gate is lawful, and
appear only in formal gate witness reports. They are not runtime or
connectivity claims.

- `PASS` means the gate completed validly and its acceptance criteria were
  satisfied. It cites evidence and does not imply connectivity beyond the
  completed gate.
- `HOLD` means the gate produced a governed result, but evidence, safety,
  custody, or preconditions do not permit advancement. `HOLD` prevents
  advancement.
- `FAILED` means the gate execution could not produce a valid governed
  result because the procedure, instrumentation, validation, or witness
  itself failed. `FAILED` prevents advancement identically to `HOLD`.
- Only `PASS` permits consideration of the next separately authorized gate.
- `FAILED` must not be silently converted into `HOLD` or `PASS`, and `HOLD`
  must not be silently converted into `PASS`.
- Unknown material operational evidence normally yields `HOLD` when the
  witness itself remains valid.
- Invalid or incomplete gate execution yields `FAILED`.

### Operational status labels

- `environment-ready`
- `bootstrap-not-run`
- `bootstrap-network-capable`
- `bootstrap-network-crossing-yes`
- `bootstrap-network-crossing-no`
- `bootstrap-network-crossing-unknown`
- `token-state-unproven`
- `token-custody-preflight-passed`
- `token-custody-preflight-held`
- `market-data-not-authorized`
- `account-observation-not-authorized`
- `execution-authority-absent`

Operational status labels describe observed system state. They do not
themselves authorize advancement, and an operational status must never
substitute for a `PASS` gate verdict.

## 14. Stop condition for 004B-1

Stop after:

- environment and bootstrap boundaries are corrected,
- credential, token, and configuration-retrieval custody is explicit,
- market-data and account-observation authority remain separate,
- no broker request has been made,
- no SDK client has been constructed,
- no token or live fixture has been created.
