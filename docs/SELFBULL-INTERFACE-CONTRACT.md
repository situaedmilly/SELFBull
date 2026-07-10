# SELFBULL Interface Contract — v1 (DESIGN-FIRST, written before any port)

> **Status:** contract sealed before implementation, per the SELFBULL-001
> canonicalization command. No Python code in this repo may exist for these
> envelopes until this document names their shape. Field names below are
> broker-neutral; enum-typed values cited within SELFBull's own vocabulary
> (side, order_type, time_in_force, asset_class) are copied from the
> official `webull-inc/webull-openapi-python-sdk` source (see footnote),
> inspected read-only at `~/Projects/_reference/webull-openapi-python-sdk`
> — never vendored, never imported, never installed.

## 0. The boundary this contract enforces

```
SELFQUANT (crown)                         SELFBull (hand)
  intelligence, observer state               Webull authentication boundary
  doctrine                                   Webull market/account translation
  shared trading schemas                     Webull order vocabulary
  AdapterGate                                broker capability discovery
  governed_decision()                        paper-order serialization
  execution authority                        live transport quarantine
  human approval                             broker audit receipts
```

SELFBull emits broker-neutral facts and prepared intents.
SELFQUANT alone decides whether an intent may advance.

**No submodule. No copied governor. No direct `selfquant.*` import inside
SELFBull.** Every envelope below is a JSON-serializable primitive structure
— dict/list/str/int/float/bool/null only, once serialized. No repo ever
imports the other's Python code; the wire is JSON, not a shared class.

## 1. `BrokerCapabilitySnapshot`

What SELFBull can currently do, self-reported. SELFQUANT reads this to
decide what it may ask for — it never grants SELFBull authority by reading it.

| Field | Type | Notes |
|---|---|---|
| `schema_version` | string | `"1.0"` for this contract |
| `broker` | string | `"webull"` |
| `adapter_version` | string | SELFBull package version |
| `observed_at` | string | ISO-8601 UTC |
| `environment` | string | `"sandbox"` \| `"production"` |
| `capabilities` | array[string] | e.g. `"paper_order_representation"`, `"credential_presence_check"` |
| `live_transport_available` | bool | Always `false` in Phase 1 — no transport client exists |
| `live_transport_enabled` | bool | SELFBull's own local flag; independent of SELFQUANT's `BROKER_LIVE_ROUTE_AVAILABLE`. Always `false` in Phase 1 |
| `kill_switch_active` | bool | SELFBull's own local kill switch, checked before every adapter action |
| `credential_state` | object | `{"app_key_id_present": bool, "app_key_secret_present": bool, "app_key_id_prefix": string\|null}` — never a secret value |
| `evidence` | object | free-form provenance (source file hashes, doc URLs consulted, etc.) |

## 2. `MarketObservationEnvelope`

| Field | Type | Notes |
|---|---|---|
| `schema_version` | string | `"1.0"` |
| `broker` | string | `"webull"` |
| `observed_at` | string | ISO-8601 UTC |
| `instrument` | object | `{"symbol": str, "instrument_type": str}` — `instrument_type` from `WebullInstrumentType`¹ |
| `quote` | object\|null | opaque — Phase 1 never populates this (no market-data call exists) |
| `session` | string\|null | e.g. `"core"`, `"extended"` — undocumented in the inspected SDK surface; left null until confirmed |
| `source` | string | `"phase1_stub"` in Phase 1 — never a real feed name until Phase 2+ |
| `freshness` | string\|null | ISO-8601 age marker; null when no data was fetched |
| `evidence` | object | provenance — always shows `"network_call": false` in Phase 1 |

## 3. `AccountObservationEnvelope`

| Field | Type | Notes |
|---|---|---|
| `schema_version` | string | `"1.0"` |
| `broker` | string | `"webull"` |
| `observed_at` | string | ISO-8601 UTC |
| `account_ref` | object | `{"account_id": str\|null, "account_type": str\|null}` — `account_type` from `WebullAccountType`¹ (`MARGIN`/`CASH`) |
| `balances` | object\|null | opaque pass-through — the inspected SDK builds request objects only; it defines no typed balance response fields (no `buying_power`/`cash_balance` names appear in source), so none are invented here |
| `positions` | array\|null | opaque pass-through, same reasoning |
| `open_orders` | array\|null | opaque pass-through, same reasoning |
| `restrictions` | array[string] | e.g. `"phase1_no_network"` |
| `evidence` | object | provenance, `"network_call": false` in Phase 1 |

## 4. `PreparedOrderIntent`

| Field | Type | Notes |
|---|---|---|
| `schema_version` | string | `"1.0"` |
| `intent_id` | string | locally generated (`uuid4`), never a broker order id |
| `broker` | string | `"webull"` |
| `created_at` | string | ISO-8601 UTC |
| `instrument` | string | symbol, e.g. `"AAPL"` |
| `asset_class` | string | from `WebullInstrumentType`¹ — `STOCK`/`ETF`/`UNIT`/`WARRANT`/`RIGHT`/`CALL_OPTION`/`PUT_OPTION` |
| `side` | string | from `WebullOrderSide`¹ — `BUY`/`SELL`/`SHORT` |
| `order_type` | string | from `WebullOrderType`¹ — `MARKET`/`LIMIT`/`STOP_LOSS`/`STOP_LOSS_LIMIT`/`TRAILING_STOP_LOSS`/`ENHANCED_LIMIT`/`AT_AUCTION`/`AT_AUCTION_LIMIT`/`ODD_LOT_LIMIT`/`MARKET_ON_OPEN`/`MARKET_ON_CLOSE` |
| `quantity` | number | |
| `limit_price` | number\|null | |
| `stop_price` | number\|null | |
| `time_in_force` | string | from `WebullOrderTIF`¹ — `DAY`/`GTC`/`IOC` |
| `extended_hours` | bool | |
| `client_order_id` | string\|null | caller-supplied idempotency key |
| `source_decision_id` | string\|null | SELFQUANT's `AgentDecisionTrace` reference — opaque string to SELFBull, never interpreted |
| `human_approval_id` | string\|null | evidence a human approved, **not** authority — see invariant below |
| `execution_authority` | bool | **always `false`**; not a constructor parameter — structurally impossible to set `true` from SELFBull |
| `transport_status` | string | one of `"simulated"` \| `"blocked"` \| `"unavailable"` — **no live-submission status exists in Phase 1** |
| `evidence` | object | provenance |

### Hard invariants (repeated because they are load-bearing)

1. `execution_authority` is always `false` inside SELFBull Phase 1 — enforced structurally (the field is not settable via any public constructor argument), not by convention.
2. `transport_status` is one of `simulated` / `blocked` / `unavailable`. No fourth value exists — there is no enum member for a live/submitted state in Phase 1.
3. SELFBull does not decide whether an intent is valid. It represents and reports; SELFQUANT's `governed_decision()` alone judges.
4. SELFQUANT may send an already-governed intent in a future phase — SELFBull's job then is still only to attempt (or refuse) transport, never to re-judge.
5. SELFBull independently refuses live transmission unless its own later transport gate is explicitly enabled — a second, broker-local check, never a replacement for SELFQUANT's governance.
6. Human approval metadata (`human_approval_id`) is evidence, not sufficient execution authority — its presence never flips `execution_authority`.

## 5. Wire format

JSON only. No pickled objects, no shared Python classes, no cross-repo
imports. SELFQUANT and SELFBull each implement their own (de)serializer for
these shapes independently; drift is caught by each side's own test suite
asserting the field list above, not by a shared schema library (a shared
package was ruled out as premature — see canonicalization command).

## 6. Versioning

`schema_version` starts at `"1.0"`. Any field addition is additive-only
(new optional field) until both sides agree to bump to `"2.0"` — bumping is
a cross-repo conversation, not a unilateral change in either repo.

---

¹ Enum vocabulary source: `webull-inc/webull-openapi-python-sdk`,
`webull/trade/common/{order_side,order_type,order_status,order_tif,
instrument_type,account_type,markets,currency,category}.py`, inspected
2026-07-09 at `~/Projects/_reference/webull-openapi-python-sdk` (reference
clone, read-only, not part of this package's dependency graph). Corrects
earlier documentation-page assumptions: credentials are `app_key_id` /
`app_key_secret` (not `app_key`/`app_secret`); `InstrumentType` has no
`EQUITY` member (`STOCK` is correct); `OrderStatus` has no `WORKING` member
(`SUBMITTED` is correct); `OrderType` has no `LIMIT_ON_OPEN` member.
