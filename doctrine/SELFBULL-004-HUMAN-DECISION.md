# SELFBULL-004A Human Decision - Custody and Observation Contract Foundation

> Status: human decision record for SELFBULL-004A only.

## Decision token

`AUTHORIZE_SELFBULL_004A_CUSTODY_AND_OBSERVATION_CONTRACT_FOUNDATION`

## Authorized action

Create the SELFBULL-004A doctrine and documentation boundary for:

- custody and witness contract,
- credential law,
- raw witness admission law,
- normalization law,
- CLI / MCP / SDK / parity boundary law.

## Authorized files

- `.gitignore`
- `doctrine/SELFBULL-004-SCOPE.md`
- `doctrine/SELFBULL-004-HUMAN-DECISION.md`
- `docs/SELFBULL-004-CREDENTIAL-CUSTODY.md`
- `docs/SELFBULL-CLI-WITNESS-RUNBOOK.md`
- `docs/SELFBULL-MCP-READONLY-RUNBOOK.md`
- `docs/SELFBULL-004-NORMALIZATION-CONTRACT.md`

No other file may change.

## Preconditions

- Repository: `/Users/millysituated/Projects/SELFBull`
- Branch: `codex/selfbull-004-readonly-connectivity`
- Expected parent: `991fa703c20d8e81b6c12b167d8d80a9e182a671`
- Known drift before action: `.gitignore` modified locally

## Not authorized

- CLI login.
- `webull doctor`.
- CLI snapshot or bar calls.
- MCP server invocation.
- MCP authentication.
- SDK authentication.
- SDK market-data calls.
- Fixture directory creation for live captures.
- Raw witness artifact admission.
- Account observation.
- Trading tool exposure.
- Generic endpoint dispatch.
- Order placement, replacement, cancellation, or transfer.

## Required stop condition

Stop after:

- the doctrine and docs exist,
- validation runs complete,
- proof shows no file drift outside the authorized set.

## Next authorization tokens

Read-only witness capture requires a separate human decision:

`AUTHORIZE_SELFBULL_004B_READ_ONLY_WITNESS_CAPTURE`

Canonical SDK transport requires a separate human decision:

`AUTHORIZE_SELFBULL_004C_CANONICAL_SDK_TRANSPORT`

Cross-plane parity admission requires a separate human decision:

`AUTHORIZE_SELFBULL_004D_CROSS_PLANE_PARITY_ADMISSION`
