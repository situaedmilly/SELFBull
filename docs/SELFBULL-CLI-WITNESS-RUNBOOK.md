# SELFBULL CLI Witness Runbook

> Status: runbook for future SELFBULL-004B only.
> SELFBULL-004A does not authorize running these commands.

## 0. Purpose

The Webull CLI is the first human-operated authentication and diagnostic
instrument. It is used to witness environment state and deterministic
read-only market-data responses.

It is not application transport and it is not an agent runtime.

## 1. Allowed role

The CLI may be used later for:

- authentication witness,
- `webull doctor`,
- deterministic read-only snapshot probes,
- deterministic read-only bar probes,
- shape comparison against MCP and SDK results.

## 2. Forbidden role

The CLI may not be used for:

- SELFBULL application transport,
- subprocess-based production implementation,
- unrestricted agent operation,
- order-capable runtime behavior inside SELFBULL code.

No SELFBULL module may shell out to `webull`.

## 3. Future 004B witness sequence

When separately authorized, the sequence is:

```text
verify local tool presence
-> authenticate interactively
-> run doctor
-> run read-only market-data probes only
-> keep raw output ephemeral
-> scan and scrub
-> human review
-> SHA-256 registration
-> admit scrubbed derivative only
```

## 4. Planned read-only witness calls

Examples for later human-run execution:

- `webull version`
- `webull auth login --region us`
- `webull doctor`
- `webull data stock snapshot --symbol SPY`
- `webull data stock bars --symbol SPY --timespan D --count 5`

These remain examples only in 004A.

## 5. Raw witness admission law

Raw CLI output is ephemeral and non-committable by default.

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

## 6. Order-surface prohibition

The CLI exposes an order-capable administrative surface. Therefore:

- do not run order commands for SELFBULL-004B witness capture,
- do not document order commands in committed fixtures,
- do not grant the CLI to autonomous application code.

## 7. Expected derivative artifacts for a later phase

Only after review may a scrubbed derivative later include:

- command class,
- symbol,
- capture timestamp,
- scrub profile,
- stable response shape,
- stable field names,
- SHA-256 digest,
- review notes.

Raw account identifiers, profile paths, request IDs, entitlements, and
token diagnostics must not be committed unless explicitly transformed into
approved scrubbed placeholders.
