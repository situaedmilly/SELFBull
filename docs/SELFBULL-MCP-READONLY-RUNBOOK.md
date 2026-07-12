# SELFBULL MCP Read-Only Runbook

> Status: runbook for future SELFBULL-004B only.
> SELFBULL-004A does not authorize starting the MCP server or performing
> authentication.

## 0. Purpose

Local MCP is the bounded agent observation plane for Webull market data.
Its initial role is narrower than the CLI:

- read-only market-data observation only,
- tool-scoped responses only,
- no trading surface,
- no account surface in 004A.

## 1. Initial toolset boundary

Initial admitted toolset:

- `market-data` only.

Not admitted in 004A:

- account tools,
- trading tools,
- broad combined toolsets,
- fixture admission without scrubbing and review.

## 2. Credential passing law

Credentials are passed only through process environment at runtime.

Credentials do not belong in:

- chat content,
- source files,
- Git history,
- JSON fixtures,
- docs,
- tests,
- logs.

For SELFBULL-004A, the authoritative custody boundary also prohibits
credential values from entering:

- exceptions,
- screenshots,
- shell transcripts,
- pull-request bodies,
- exported manifests,
- Google Drive manifests.

Only presence / missing state may be reported.
Masked previews remain prohibited in SELFBULL-004A.

## 3. Future 004B witness sequence

When separately authorized:

```text
verify MCP executable presence
-> configure runtime environment
-> authenticate in the MCP custody plane
-> enumerate allowed tools
-> call only approved market-data tools
-> keep raw output ephemeral
-> scan and scrub
-> human review
-> SHA-256 registration
-> admit scrubbed derivative only
```

## 4. Planned initial read-only tools

Examples of the intended initial witness surface:

- `get_stock_snapshot`
- `get_stock_bars_single`
- `get_stock_quotes`
- `get_stock_tick`
- `get_stock_footprint`
- `get_stock_noii_snapshot`

These are expected witness targets, not yet admitted fixtures.

## 5. Raw witness admission law

Raw MCP output is ephemeral and non-committable by default.

Required pipeline:

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

## 6. Agent boundary

MCP is an agent observation plane only.

It is not:

- canonical application transport,
- evidence of canonical parity by itself,
- authorization to expand into account or trading tools.

## 7. Expected derivative artifacts for a later phase

Only after review may a scrubbed derivative later preserve:

- tool name,
- stable parameter class,
- stable response shape,
- stable field names,
- scrub profile,
- SHA-256 digest,
- review notes.

Identity-bearing metadata, unstable request identifiers, token state, and
non-essential host details must be removed or classified before any
fixture admission.
