# SELFBull → SELFQUANT Observation Adapter Plan — DESIGN ONLY

> **Status: DESIGN ONLY.** Nothing in this document is implemented.
> SELFQUANT was not mutated to produce this plan — it lives entirely in
> SELFBull's own `docs/`, describing SELFBull's side of a future,
> separately authorized exchange. No code in either repository implements
> what follows yet. This is the reverse direction of
> `docs/SELFQUANT-INTEGRATION-PLAN.md`, which describes SELFQUANT pushing
> `PreparedOrderIntent` to SELFBull — that document and the adapter it
> describes are untouched by this plan and remain a separate, structurally
> inert design.

## The future exchange

```
SELFBull MCP snapshot output
   -> SELFQUANT ObservationProvider adapter
   -> SELFQUANT normalization
   -> SELFQUANT checkpoint ledger
   -> REEfrequency
```

SELFBull produces one thing: an admitted, redacted snapshot receipt from
its single governed MCP tool (`get_stock_snapshot`, scoped by PR #5's
one-tool composition layer, subject to the extended-hours request-mode
contract in `docs/SELFBULL-EXTENDED-HOURS-REQUEST-MODE.md`). Everything
downstream of that receipt — naming it as a checkpoint, timestamping it,
normalizing it, writing it to a ledger, and handing it to REEfrequency — is
SELFQUANT's responsibility, implemented in the SELFQUANT-2026 repository,
not here.

## Ownership boundaries

### SELFBull owns

- Exposing exactly one governed MCP tool (`get_stock_snapshot`).
- Returning an admitted, redacted snapshot receipt — the same
  `snapshot_receipt_admission` pipeline PR #5 introduces (secret scan,
  identity scan, formatter-contract validation, admitted-field allowlist).
- The `REGULAR` / `EXTENDED` / `OVERNIGHT` request-mode contract.

SELFBull does **not**:

- know or accept checkpoint names (`premarket`, `open_plus_15m`, etc.),
- assign or interpret `observed_at` beyond what the broker-reported
  snapshot itself carries,
- write to any SELFQUANT ledger, file, or database,
- call REEfrequency or know that it exists at runtime,
- push data anywhere — it only returns a receipt to a caller that already
  holds MCP invocation authority.

### SELFQUANT owns (future work, in the SELFQUANT-2026 repo — not built here)

- Checkpoint names and the mapping from a checkpoint to a request.
- Capture-time `observed_at` assignment and normalization.
- Ledger persistence and replay.
- The adapter itself:
  `selfquant/adapters/selfbull_mcp_observation_provider.py` — a client
  that calls SELFBull's MCP tool, receives the admitted receipt, and folds
  it into SELFQUANT's own observation schema. This file does not exist yet
  and is not created by this plan.

### REEfrequency owns

- Consuming plain JSON checkpoint observations from SELFQUANT's ledger.
- Measurement only — no capture, no normalization, no broker contact.

## What would need to change (future, not now)

**In SELFBull:**
- Nothing beyond what PR #5 and the extended-hours contract already
  define. SELFBull's snapshot receipt shape is the entire interface
  surface this plan depends on; no SELFQUANT-aware code is added to
  SELFBull.

**In SELFQUANT (out of scope for this repository):**
- `selfquant/adapters/selfbull_mcp_observation_provider.py`: calls
  SELFBull's MCP tool (or a transport wrapping it), receives the admitted
  receipt, and converts it into a SELFQUANT `MarketObservation`.
- Whatever transport carries the MCP call from SELFQUANT's process to
  SELFBull's tool — not decided here, mirrors the open transport question
  in `docs/SELFQUANT-INTEGRATION-PLAN.md`.
- Checkpoint-name assignment logic that decides which SELFBull request
  (with which `RequestMode`) corresponds to which checkpoint.

## Blocking condition

Implementation of the adapter — on either side — remains blocked until:

1. PR #5 merges and is independently reviewed.
2. The extended-hours request-mode contract
   (`docs/SELFBULL-EXTENDED-HOURS-REQUEST-MODE.md`) is implemented and
   reviewed on its own, per its own blocking condition.
3. A separate field-admission gate review seals which snapshot fields the
   adapter is allowed to carry across the SELFBull/SELFQUANT boundary.

None of these three conditions are satisfied as of this document. No
Gate C authorization exists in SELFBull (`doctrine/SELFBULL-004-SCOPE.md`
§3) and no live SPY witness is authorized in either repository.

## Non-goals of this document

- Does not choose a transport mechanism between the two repos.
- Does not implement anything in either repository.
- Does not modify `docs/SELFQUANT-INTEGRATION-PLAN.md` or the
  `PreparedOrderIntent` / `BrokerTransportReceipt` design it describes —
  that is the unrelated, opposite-direction order-intent flow.
- Does not authorize any live broker request, live MCP authentication, or
  live SPY capture. Those remain gated exactly as described in
  `doctrine/SELFBULL-004-SCOPE.md` and
  `docs/SELFBULL-MCP-READONLY-RUNBOOK.md`.
