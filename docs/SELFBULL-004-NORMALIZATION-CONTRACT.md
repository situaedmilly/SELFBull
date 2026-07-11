# SELFBULL-004 Normalization Contract

> Status: normalization doctrine for SELFBULL-004A only.
> No transport implementation is authorized by this document.

## 0. Purpose

This document defines the factual normalization boundary for authenticated
market observations.

SELFBULL-004 does not merge provenance, confidence, transport receipts, and
market facts into one object.

It preserves three distinct artifacts:

- `MarketObservation`
- `TransportReceipt`
- `RawWitnessReference`

## 1. Normalization law

Rules:

- preserve only observed facts,
- missing values remain `null`,
- unknown fields remain explicit,
- local capture time does not replace broker observation time,
- provenance is not confidence,
- evidence is not authority.

Do not introduce:

- confidence scores,
- trade interpretations,
- bullish or bearish labels,
- recommendations,
- signals,
- execution permission.

## 2. Canonical `MarketObservation` shape

```json
{
  "schema_version": "004.0",
  "observation_id": "selfbull-obs-...",
  "observed_at": null,
  "recorded_at": "2026-07-11T19:20:36Z",
  "observer": "system",
  "source": {
    "platform": "webull",
    "surface": "cli",
    "transport_plane": "cli",
    "tool_or_command": "stock_snapshot",
    "account_context": "market_data_only"
  },
  "instrument": {
    "symbol": "SPY",
    "asset_class": "stock"
  },
  "observation_type": "stock_snapshot",
  "market_state": {
    "last_price": null,
    "bid": null,
    "ask": null,
    "volume": null
  },
  "bars": [],
  "unknown_fields": [],
  "notes": null,
  "evidence": {
    "observation_authority": "broker_reported",
    "raw_fixture_id": null,
    "plane_parity_group": null
  },
  "execution_authority": false
}
```

## 3. `observed_at` law

If the broker response does not explicitly provide observation time, then:

- `observed_at` remains `null`.

`recorded_at` may record local normalization time, but it must not be
substituted for market observation time.

## 4. `TransportReceipt` law

Transport facts belong in a separate artifact, not inside market-state
normalization.

Examples of transport-receipt concerns:

- runtime plane,
- request class,
- execution timestamp,
- retry count,
- redacted environment receipt,
- read-only authorization class.

`network_call: true` does not belong inside the normalized market evidence
contract.

## 5. `RawWitnessReference` law

The raw witness reference may point to:

- raw local capture identifier,
- scrub profile,
- SHA-256 digest,
- review status,
- capture-time distance grouping.

It must not embed raw witness contents into the normalized observation.

## 6. Plane boundaries

The same `MarketObservation` shape must be usable for later normalized data
from:

- CLI witness capture,
- MCP witness capture,
- SDK transport.

Plane-specific provenance lives under:

- `source.transport_plane`
- `source.tool_or_command`
- `evidence.raw_fixture_id`
- `evidence.plane_parity_group`

## 7. Future SDK public surface boundary

When 004C is separately authorized, the SDK adapter public surface is
limited to:

- `get_stock_snapshot(symbol)`
- `get_stock_bars(symbol, timespan, count)`

No generic endpoint dispatcher.
No account client.
No trading client.
No token object returned to callers.
No SDK object exposed outside the adapter.

## 8. Parity classification law

Cross-plane parity must compare under explicit policy, not whole-object
equality.

Required classes:

- `exact_match`
- `timestamp_format_only`
- `null_vs_missing`
- `numeric_tolerance_match`
- `semantic_mismatch`
- `entitlement_mismatch`
- `unsupported_field`

Field-level comparison policy remains:

- identity fields compare under `exact_match`
- symbol and asset class compare under `exact_match`
- OHLCV compares under `exact_match` only for identical bar timestamps
- snapshot price may use `numeric_tolerance_match` only when
  capture-time separation is recorded
- null-vs-missing remains classified under `null_vs_missing`
- entitlement-dependent values remain classified under
  `entitlement_mismatch`
- unsupported payload content remains classified under `unsupported_field`
- semantic drift remains a hard failure under `semantic_mismatch`

Every parity report must record capture-time distance between planes.
