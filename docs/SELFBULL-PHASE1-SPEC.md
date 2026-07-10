# SELFBULL — Phase 1 Spec (WEBULL BROKER-SURFACE MODEL · NOT ACTIVATED)

> **Status: PHASE 1.** SELFBull Phase 1 is a Webull broker-surface model:
> offline, unauthenticated, non-networked, non-executing, independently
> testable, contract-driven. No Webull credential is read from anywhere but
> an environment variable presence-checked at runtime (never persisted,
> never printed). No HTTP call exists anywhere in this package. No order —
> paper or otherwise — ever reaches Webull.

## 0. What Phase 1 is

| Organ | Component | State |
|---|---|---|
| Vocabulary | Webull-documented enums (side, order type, TIF, instrument type, account type, market, currency) | ✅ ported from official SDK source, cited |
| Credential boundary | presence-only check of two env vars | ✅ present/missing + short App Key ID preview only |
| Config validator | shape check of env-var names | ✅ never inspects a secret value |
| Read plane | `get_account_list` / `get_account_balance` / `get_quote` | ⛔ stubs, raise `NotImplementedError`, no network call anywhere |
| Order plane | `PreparedOrderIntent` representation | ✅ local object, `execution_authority` structurally pinned `false` |
| Live transport | `submit` / `cancel` / `replace` / `transfer` | ⛔ refuse unconditionally — no implementation exists |
| Audit plane | redacted JSONL event log | ✅ secrets scrubbed before any write |
| Cross-repo contract | `docs/SELFBULL-INTERFACE-CONTRACT.md` | ✅ sealed before any code was ported |

## 1. Allowed capabilities (Phase 1)

- Validate public configuration shape (env var names, not values).
- Report credential presence without printing values.
- Represent documented broker vocabulary (enums sourced from the official SDK, not memory).
- Create simulated `PreparedOrderIntent` objects.
- Emit redacted audit events.
- Report broker capabilities (`BrokerCapabilitySnapshot`).
- Refuse every live transport request.

## 2. Forbidden capabilities (Phase 1) — walls, not features to add later

- Quote retrieval
- Account retrieval
- Login
- Refresh-token handling
- Order preview through Webull
- Order placement
- Cancellation
- Replacement
- Transfer
- Autonomous decision-making
- Background execution

## 3. Vocabulary source (no assumption from memory)

Every enum value in `src/selfbull/contracts.py` is copied from
`webull-inc/webull-openapi-python-sdk`, inspected read-only at
`~/Projects/_reference/webull-openapi-python-sdk` (not vendored, not a
dependency, not imported by this package). Where the SDK does not define a
typed shape (account balance/position response fields), this package
carries the value as an opaque `dict`/`list` rather than inventing field
names. See the interface contract's footnote for the exact corrections this
made versus an earlier documentation-page draft (credential field names,
`InstrumentType` values, `OrderStatus` values, `OrderType` values).

## 4. Credential model

Two environment variables, presence-checked only:

- `SELFBULL_WEBULL_APP_KEY_ID` — maps to the SDK's `AppKeyCredential.app_key_id`
- `SELFBULL_WEBULL_APP_KEY_SECRET` — maps to the SDK's `AppKeyCredential.app_key_secret`

`check_credentials()` returns present/missing booleans plus an at-most
4-character preview of the App Key ID only. The App Key Secret gets **no**
preview at all — present/missing only, because it is the more sensitive
half of the credential pair. No credential value is ever logged, printed,
or persisted anywhere in this repository.

## 5. Kill switch

SELFBull carries its own local kill switch (`SELFBULL_STOP` env var, or a
`selfbull/STOP` sentinel file at the repo root), independent of SELFQUANT's
kill switches. Any adapter action checks it first; if tripped, every
capability reports `kill_switch_active: true` and every attempted action
refuses.

## 6. Cross-repo boundary (see the interface contract for full detail)

SELFBull emits `BrokerCapabilitySnapshot`, `MarketObservationEnvelope`,
`AccountObservationEnvelope`, and `PreparedOrderIntent` — all JSON only, no
shared Python class. SELFQUANT alone runs `governed_decision()`. SELFBull
never imports `selfquant.*`; SELFQUANT never imports `selfbull.*` in this
phase (Phase 8's `SELFQUANT-INTEGRATION-PLAN.md` is design-only).

## 7. Rollback plan

- **Not installed yet** → rollback is trivial: nothing depends on this
  package; delete the clone. No state to unwind.
- **If a future phase's transport layer misbehaves** → the local kill
  switch halts every adapter action immediately; no live orders exist to
  cancel because Phase 1 places none.
- **Full teardown** → delete `~/Projects/SELFBull`; revoke/rotate the two
  env vars if they were ever set; SELFQUANT is entirely unaffected since it
  never imported this package.

## 8. Tests required before any Phase 2 authorization

All twenty guarantees in `tests/` must pass with the standard library only
(`python3 -m unittest discover -s tests -v`) before any network client,
dependency, or credential-reading code is proposed:

1. Package imports without SELFQUANT installed.
2. No source file imports `selfquant`.
3. No source file imports `rbhcb`.
4. No credential literal exists in source.
5. Credential state exposes present/missing only.
6. Audit records redact token/password/secret-like material.
7. `PreparedOrderIntent` is JSON serializable.
8. `PreparedOrderIntent.execution_authority` is always `false`.
9. A caller cannot construct `execution_authority=true`.
10. Human approval metadata does not enable transport.
11. Kill switch blocks all adapter actions.
12. Live transport is unavailable.
13. Submit refuses.
14. Cancel refuses.
15. Replace refuses.
16. Transfer refuses.
17. No network call occurs during import or tests.
18. Official Webull values used in contracts match cited documentation.
19. Manifest accurately reports Phase 1.
20. Existing SELFQUANT protected-file hashes remain unchanged.

**Phase-2 gate:** any HTTP client, dependency install, or credential-reading
implementation happens only after every test above passes AND is explicitly
authorized in a separate session — mirroring the RBHCB Phase-2/3 split
already established in SELFQUANT.

---

*Spec written 2026-07-09/10. Design-first: this document and the interface
contract were sealed before any Phase 1 module was ported. No credentials
stored, no Webull login implemented, no network call exists, no live
trading. SELFBull is a canonical, standalone, non-executing Webull
broker-surface repository. SELFQUANT remains the sole authority and
decision plane. No live broker transport exists.*
