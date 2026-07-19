# SELFBULL-004B Snapshot Receipt Admission Design

> Status: design-only boundary after the one-tool live SPY witness.
> This document does not authorize another broker request, fixture creation,
> response parsing, normalization implementation, SDK work, or Git admission.

## 0. Purpose

Define how evidence from the sealed `get_stock_snapshot` MCP aperture may move
from ephemeral broker output toward a reviewed fixture candidate without
collapsing transport proof into market observation.

The live witness proved:

- the visible MCP surface is exactly `get_stock_snapshot`,
- canonical `{"symbol": "SPY"}` is admitted as `{"symbols": "SPY"}`,
- optional MCP arguments are omitted so their reviewed safe defaults apply,
- one broker request returns a `CallToolResult`,
- broker content is carried as formatted text under
  `structuredContent.result`, not as top-level market fields.

Formatted broker text is not a normalized observation merely because the MCP
invocation succeeded.

## 1. No reconstruction from destroyed evidence

**NO RECONSTRUCTION FROM DESTROYED EVIDENCE.**

The successful live SPY response was destroyed. No raw payload remains. No
parser fixture may be invented from memory, no market value may be inferred or
recreated, and no formatter line may be reconstructed.

That witness proves only:

- the one-tool composition worked,
- one request completed,
- a `CallToolResult` existed,
- `structuredContent.result` contained formatted content,
- no authentication, entitlement, protocol, or timeout error occurred,
- raw custody and destruction laws passed.

It does not prove surviving prices, timestamps, bid/ask values, volume, parser
fields, fixture contents, or normalized observations. Every future evidence
admission requires a fresh, separately authorized capture.

## 2. Artifact separation

The admission process preserves three distinct artifacts.

### 2.1 `TransportReceipt`

Value-free proof about the transport event. Its required identity and state
fields are:

- `transport_receipt_id`,
- `schema_version`,
- `capture_session_id`,
- `transport_plane`,
- `tool_name`,
- visible tool names,
- canonical and admitted argument field names,
- exact-surface result,
- request budget and `broker_request_count`,
- `lifecycle_status`,
- `custody_status`,
- completion and timeout classifications,
- result container type,
- authentication, entitlement, and protocol error booleans,
- raw-evidence destruction state,
- fixture-admission state,
- `execution_authority = false`.

It must not retain market values, raw arguments, complete timestamps, request
identifiers, schemas, token material, account identity, or raw response text.
It is immutable after creation. A correction receives a new identity and an
explicit revision reference.

### 2.2 `ScrubbedSnapshotDerivative`

A factual derivative created only after exact parsing and scrubbing are
separately implemented and reviewed. It may contain broker-reported market
facts, but it is not admitted merely by being generated.

Its required identity and review fields are:

- `derivative_id`,
- `parser_version`,
- `source_package`,
- `source_package_version`,
- `formatter_shape_id`,
- `raw_reference_id`,
- `transport_receipt_id`,
- `revision_of`,
- `admitted_field_names`,
- `rejected_field_names`,
- `ambiguous_field_names`,
- `parse_status`,
- `human_review_status`,
- `execution_authority = false`.

It is an immutable candidate. Correction creates a new derivative rather than
mutating the prior artifact.

### 2.3 `RawWitnessReference`

A non-content reference to the ephemeral capture and its custody state. It may
record a local capture identifier, scrub profile, and review state. It must not
embed raw broker output, point to a committed raw file, or carry the
derivative's identity or hash.

Its required fields are:

- `raw_reference_id`,
- `capture_session_id`,
- `capture_started_at`,
- `capture_recorded_at`,
- `source_plane`,
- `tool_name`,
- `raw_destroyed`,
- `destruction_verified`,
- `raw_content_retained = false`,
- `repository_path = null`,
- `fixture_id = null`.

`TransportReceipt`, `ScrubbedSnapshotDerivative`, and `RawWitnessReference`
identities are distinct and never interchangeable.

## 3. Required custody sequence

```text
fresh separately authorized capture
-> protected ephemeral raw chamber
-> secret-pattern scan
-> identity-pattern scan
-> formatter-shape classification
-> bounded parser
-> scrubbed derivative candidate
-> human review
-> approval or rejection
-> SHA-256 registration of approved scrubbed derivative
-> separate fixture-admission authorization
-> governed ledger integration
```

Raw output remains non-committable by default. No stage may be skipped because
the transport succeeded.

## 4. Transport receipt contract

The future receipt implementation must be equivalent to this value-free
shape:

```json
{
  "transport_receipt_id": "selfbull-transport-...",
  "schema_version": "004B.snapshot-transport-receipt.v1",
  "capture_session_id": "selfbull-capture-...",
  "transport_plane": "webull_mcp_custom_composition",
  "tool_name": "get_stock_snapshot",
  "visible_tool_names": ["get_stock_snapshot"],
  "exact_surface_match": true,
  "canonical_argument_field_names": ["symbol"],
  "admitted_argument_field_names": ["symbols"],
  "optional_arguments_forwarded": false,
  "broker_request_budget": 1,
  "broker_requests_executed": 1,
  "lifecycle_status": "CLOSED",
  "custody_status": "RAW_DESTROYED",
  "invocation_completed": true,
  "result_container_type": "CallToolResult",
  "result_payload_class": "formatted_text",
  "authentication_error_present": false,
  "entitlement_error_present": false,
  "protocol_error_present": false,
  "raw_output_committed": false,
  "raw_output_destroyed": true,
  "fixture_admitted": false,
  "sdk_called": false,
  "execution_authority": false
}
```

The symbol value is intentionally absent from the transport receipt. Symbol
identity belongs in the reviewed market observation and may be proven through
the derivative admission process.

## 5. Formatter-version and parser boundary

The future implementation must preserve these layers:

```text
MCP protocol envelope
-> CallToolResult container
-> structuredContent container
-> formatter-produced result content
-> parsed factual market fields
```

Formatted MCP content is not normalized evidence. It must not be assumed to be
JSON, stable across package versions, semantically complete, safe to admit
without parsing, or broker timestamped.

No generic table parser, permissive regular expression collection, or
best-effort field guessing is admitted by this design.

A future parser accepts only a fresh protected raw capture and produces either
a `ScrubbedSnapshotDerivative` candidate or a controlled refusal receipt. It
must bind admission to:

- `webull-openapi-mcp` package version,
- MCP protocol result type,
- `formatter_shape_id`,
- `parser_version`,
- an exact recognized field layout.

Unknown package versions or formatter shapes fail closed. The parser output
must include:

- `parser_version`,
- `source_package`,
- `source_package_version`,
- `formatter_shape_id`,
- `parse_status`,
- `admitted_field_names`,
- `rejected_field_names`,
- `ambiguous_field_names`,
- `observed_at_source`,
- `raw_reference_id`,
- `transport_receipt_id`,
- `execution_authority = false`.

Required controlled failure classes are:

- `UNKNOWN_FORMATTER_SHAPE`,
- `UNSUPPORTED_PACKAGE_VERSION`,
- `STRUCTURED_CONTENT_MISSING`,
- `RESULT_CONTAINER_MISSING`,
- `REQUIRED_FIELD_MISSING`,
- `AMBIGUOUS_FIELD`,
- `VALUE_TYPE_INVALID`,
- `SYMBOL_MISMATCH`,
- `TIMESTAMP_UNAVAILABLE`,
- `SECRET_PATTERN_PRESENT`,
- `IDENTITY_PATTERN_PRESENT`,
- `PARSER_INTERNAL_ERROR`.

A future offline parser must also:

1. consume fictional formatted snapshots before any broker output,
2. require one reviewed formatter version or shape,
3. require exactly one requested instrument,
4. preserve broker field names before normalization,
5. distinguish missing fields from explicit nulls,
6. preserve unknown fields for review,
7. reject duplicate headings or ambiguous row boundaries,
8. reject account, order, watchlist, or trading vocabulary,
9. reject credential, token, signature, path, and request-identity patterns,
10. emit no interpretation, signal, confidence, recommendation, or execution
    authority.

It may not fabricate missing values, substitute timestamps, parse fallback
prose, infer broad schemas, create recommendations, calculate confidence,
express order intent, or create a trade thesis.

If the formatted response does not explicitly provide broker observation
time, `observed_at` remains `null`. Local capture time may become
`recorded_at`; it may not masquerade as market observation time.

## 6. Scrubbed derivative candidate

The future derivative may be equivalent to:

```json
{
  "schema_version": "004B.snapshot-derivative.v1",
  "derivative_id": "selfbull-derivative-...",
  "transport_receipt_id": "selfbull-transport-...",
  "raw_reference_id": "selfbull-raw-reference-...",
  "revision_of": null,
  "source_plane": "webull_mcp_custom_composition",
  "tool_name": "get_stock_snapshot",
  "parser_version": "004B.snapshot-parser.v1",
  "source_package": "webull-openapi-mcp",
  "source_package_version": "<reviewed version>",
  "formatter_shape_id": "<reviewed shape>",
  "parse_status": "PENDING",
  "observed_at_source": "BROKER_EXPLICIT_OR_NULL",
  "instrument": {
    "symbol": "SPY",
    "asset_class": "stock"
  },
  "observed_at": null,
  "recorded_at": "<local UTC capture time>",
  "broker_field_names": [],
  "admitted_field_names": [],
  "rejected_field_names": [],
  "ambiguous_field_names": [],
  "market_fields": {},
  "null_field_names": [],
  "unknown_fields": [],
  "scrub_profile": "004B.snapshot.v1",
  "human_review_status": "PENDING",
  "sha256_registration": null,
  "fixture_admitted": false,
  "execution_authority": false
}
```

Placeholders in this design are not fixture values and must not be copied into
tests as purported broker evidence.

## 7. Field-admission taxonomy

### Allowed factual candidates

- symbol,
- last price,
- bid,
- ask,
- volume,
- broker-provided market timestamp,
- factual market-status fields,
- delayed/real-time indicator when explicitly supplied.

### Conditional fields

- spread, only when bid and ask are independently admitted,
- formatter-version-dependent fields,
- entitlement labels,
- session-state labels,
- fields requiring explicit semantic mapping.

### Forbidden fields

- bullish or bearish labels,
- recommendations,
- predictions,
- confidence scores,
- entry or exit instructions,
- targets,
- stop loss or take profit,
- order intent,
- trade intent,
- portfolio action,
- execution authority.

Missing values remain `null`. No parser fallback may fabricate them.

## 8. Refusal conditions

Return a controlled refusal and admit no derivative when:

- the visible MCP surface differs from exactly one tool,
- more than one broker request is associated with the receipt,
- the admitted MCP argument surface differs from exactly `symbols`,
- optional MCP arguments were forwarded,
- the result is missing, timed out, or carries an auth, entitlement, or
  protocol error,
- the formatter shape is unknown or ambiguous,
- the returned symbol cannot be proven exactly,
- multiple symbols or rows are present,
- required factual fields are duplicated or malformed,
- missing and null cannot be distinguished,
- secret, token, signature, account identity, profile path, request ID, or
  trace metadata is detected,
- unknown fields have not received human review,
- `execution_authority` is anything other than `false`.

Refusal does not authorize another broker request.

## 9. Temporal truth

- `observed_at` is broker observation time only.
- `observed_at` remains `null` unless Webull explicitly provides it.
- `recorded_at` is local capture time only.
- `recorded_at` never substitutes for `observed_at`.
- transport completion time is not market observation time.
- formatter timestamp ambiguity causes refusal or a null factual field under
  the reviewed parser contract.
- capture-time distance belongs in later parity analysis.
- correction creates a new immutable revision; it never mutates the prior
  artifact.

Complete timestamps do not enter the value-free `TransportReceipt`.

## 10. Admission states

The closed state progression is:

```text
EPHEMERAL_CAPTURED
-> CLASSIFIED
-> SCRUBBED_PENDING_HUMAN_REVIEW
-> REVIEWED_PENDING_SHA256
-> READY_FOR_FIXTURE_ADMISSION
-> ADMITTED
```

Only a separate human authorization may transition
`READY_FOR_FIXTURE_ADMISSION` to `ADMITTED`.

## 11. SHA-256, fixture, and revision law

- raw response content is not committed or registered as a fixture,
- a raw-response hash grants no retention authority,
- SHA-256 registration applies only to a human-approved scrubbed derivative,
- fixture admission requires distinct authorization,
- rejected derivatives remain non-canonical,
- corrected derivatives receive a new identity and hash,
- no admitted fixture may overwrite an earlier fixture,
- transport receipts and derivatives have distinct identities and hashes,
- no self-referential manifest hash is required.

The golden specimen is the human-reviewed scrubbed derivative. Raw broker
output is never the golden specimen.

## 12. Existing infrastructure integration

SELFBULL already contains:

- `snapshot_ledger.py`,
- observation normalization infrastructure,
- append-only revision behavior,
- retrospective replay,
- factual delta vocabulary.

Those systems are not rebuilt by this phase. The missing work is governed,
additive integration:

```text
ScrubbedSnapshotDerivative
-> live observation adapter
-> existing normalization contract
-> existing append-only snapshot ledger
-> existing replay and delta systems
```

Receipt admission produces evidence candidates. Existing downstream systems
retain their sealed responsibilities.

## 13. Future implementation scope

The smallest initial implementation surface is:

- `src/selfbull/snapshot_receipt_admission.py`,
- `tests/test_snapshot_receipt_admission.py`.

Optional later integration is limited to:

- `src/selfbull/live_snapshot_observation_adapter.py`,
- `tests/test_live_snapshot_observation_adapter.py`.

The receipt-admission module may own:

- formatter classification,
- parser dispatch by exact `formatter_shape_id`,
- scrubbed derivative construction,
- categorical refusal,
- value-free transport linkage,
- human-review state representation,
- SHA-256 calculation for approved scrubbed derivatives.

It may not own MCP startup, authentication, token custody, broker invocation,
polling, streaming, ledger interpretation, SELFQUANT analysis,
recommendations, order creation, or execution.

## 14. Authority law

`execution_authority` remains `false` in every artifact and state.

Receipt admission explicitly excludes:

- account data,
- balances,
- positions,
- orders,
- watchlists,
- trading tools,
- SDK canonical transport,
- bars admission,
- automated capture,
- unattended fixture admission,
- recommendations,
- execution.

Receipt admission is evidence custody, not market interpretation.

## 15. Inputs and outputs

Design inputs:

- the sealed one-tool composition contract,
- the fail-closed string schema-admission contract,
- the successful live transport receipt facts,
- SELFBULL-004 credential, witness, and normalization doctrine.

This design outputs only this document. It creates no parser, receipt module,
fixture, raw witness, hash, broker request, or normalized observation.

## 16. Rollback

Rollback for this design is removal of this document before commit, or a
revert of its future isolated commit. No runtime behavior changes because this
design introduces no executable code.

## 17. Next lawful phase

The next phase may design and offline-test a fictional formatted-snapshot
parser plus a value-free receipt builder. It uses fictional inputs only and
must stop before any fresh live capture or fixture admission.
