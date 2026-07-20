# SELFBull Extended-Hours Request-Mode Contract — DESIGN ONLY

> **Status: DESIGN ONLY.** Nothing in this document is implemented. No code
> in this repository defines `RequestMode`, `extend_hour_required`, or
> `overnight_required` yet. Implementation follows in a separate, later
> pass, after PR #5 (`codex/selfbull-004b-one-tool-mcp-composition`) merges
> and is independently reviewed — the same blocking condition already
> applied to the SELFQUANT observation-adapter plan below.

## Purpose

The upstream Webull MCP `get_stock_snapshot` tool accepts two raw session
booleans: `extend_hour_required` and `overnight_required`. Passed directly,
a caller could request any combination, including combinations that don't
correspond to a real trading session. This document defines a closed,
named contract that SELFBull will expose instead of the raw booleans.

## The contract

Three caller-facing modes, and no others:

| Mode | `extend_hour_required` | `overnight_required` |
|---|---|---|
| `REGULAR` | `false` | `false` |
| `EXTENDED` | `true` | `false` |
| `OVERNIGHT` | `true` | `true` |

No public constructor, function, or MCP-facing argument accepts
`extend_hour_required` or `overnight_required` directly. The only way to
select a session window is to name one of `REGULAR`, `EXTENDED`, or
`OVERNIGHT`. The mapping table above is the sole translation point.

## Rules

- **Caller-supplied, never inferred.** The mode is an explicit argument.
  SELFBull does not read the wall clock, does not consult a market
  calendar, and does not guess a mode from the time of the request.
- **No checkpoint vocabulary.** `REGULAR` / `EXTENDED` / `OVERNIGHT` are
  session-window request modes, not checkpoint names. SELFBull does not
  define or accept `premarket`, `postmarket`, `open`, `open_plus_5m`,
  `open_plus_15m`, or any other checkpoint identifier — that vocabulary
  belongs to SELFQUANT's checkpoint-capture engine, in a separate repo,
  and is out of scope here.
- **No scheduling, no polling.** This contract describes a single request's
  session-window selection. It does not introduce a scheduler, a loop, a
  retry policy, or any repeated-invocation behavior.
- **No network call.** This document, and the implementation that follows
  it, define a pure mapping (three enum values to two booleans). Neither
  makes an MCP call, starts an MCP server, or authenticates.
- **No new call site.** As of this document, `get_stock_snapshot` has no
  invocation site in `main` — PR #5 (which adds the one-tool composition
  layer) is still open. This contract has nothing to attach to yet.

## Why implementation is deferred

`doctrine/SELFBULL-004-SCOPE.md` and
`doctrine/SELFBULL-004B-MCP-COMPOSITION-SCOPE.md` both treat surface
expansion as a sequence of independently reviewed, separately authorized
steps — passing one gate does not authorize the next, and each addition to
the MCP-facing surface gets its own review. PR #5 defines the one-tool
composition boundary this contract would extend; landing new request-mode
plumbing before that boundary is merged and reviewed would add scope to an
already-open, unreviewed change rather than build on a settled one. So:

1. PR #5 merges.
2. This contract is implemented as a small, standalone addition (an enum
   and a mapping function — no new tool, no new call site beyond what
   already exists), reviewed on its own.
3. Only then does wiring it into any actual snapshot-request call site
   become a separate, later question — itself still bounded by Gate C
   (`doctrine/SELFBULL-004-SCOPE.md` §3): one bounded read-only
   market-data request, requiring its own independent human authorization.

## Non-goals

- Does not implement `RequestMode`, the mapping function, or any test for
  either — that's the later, separate pass.
- Does not modify `src/selfbull/mcp_one_tool_composition.py`,
  `src/selfbull/mcp_session_harness.py`, or `src/selfbull/mcp_inventory.py`.
- Does not authorize a live snapshot request in any mode. Gate C has not
  passed; nothing here changes that.
