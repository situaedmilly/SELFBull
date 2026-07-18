# SELFBULL-004 Credential Custody

> Status: bootstrap-boundary custody correction for SELFBULL-004B-1 only.
> No credential capture, authentication, or broker call is authorized by
> this document.

## 0. Purpose

This document defines where Webull credentials may exist, where they may
not exist, and what SELFBULL may report about them.

## 1. Allowed custody locations

Credentials may exist only in:

- runtime process environment, or
- an explicitly approved local credential store outside Git custody.

Examples of allowed runtime-only locations:

- local shell environment,
- process environment passed into an MCP server,
- process environment consumed by a future SDK adapter.

The approved SELFBull runtime variable names, the upstream SDK
fallback-name classification, and the region's non-secret status are
defined once, authoritatively, in `doctrine/SELFBULL-004-SCOPE.md` §4
("Credential law"). That definition governs these runtime-only custody
locations as well; it is not restated here.

## 2. Forbidden custody locations

Credentials may not enter:

- source code,
- Git history,
- committed fixtures,
- docs,
- tests,
- logs,
- exceptions,
- screenshots,
- shell transcripts,
- pull-request text,
- exported manifests,
- Google Drive manifests,
- copied notebook cells,
- crash reports.

Credentials also may not appear as:

- partial values,
- masked values,
- first-character or last-character previews,
- hashes of secret values,
- serialized fields,
- interpolated exception text,
- shell-history examples containing real values.

## 3. Reporting law

The present/missing-only credential reporting law and the prohibition on
full, partial, masked, first-character, last-character, and hashed
credential representations are defined once, authoritatively, in
`doctrine/SELFBULL-004-SCOPE.md` §4 ("Credential law"); they are not
restated here.

Any existing four-character App Key ID preview is noncompliant with that
custody law and must be removed in a later bounded implementation repair.
This doctrine-only correction does not modify source code.

The complete Gate B witness prohibition list (including the prohibition on
capturing market data) is defined once, authoritatively, in
`doctrine/SELFBULL-004-SCOPE.md` §3 ("Gate B - Bootstrap Witness") and is
not independently re-enumerated here. In addition to that list,
credential-adjacent output must not print:

- session cookies,
- refresh tokens,
- bearer strings.

If a future phase adds a transport receipt, the receipt must remain
redacted and must not disclose secrets.

## 4. Token custody (Gate A2 - Token-Custody Preflight)

Token state is a separate secret class. A token is not a credential
preview and must never be treated as ordinary diagnostic data.

Gate A2's inspection scope, `PASS` conditions, and `HOLD` conditions are
defined once, authoritatively, in `doctrine/SELFBULL-004-SCOPE.md` §3
("Gate A2 - Token-Custody Preflight"). That definition governs token
custody as well; it is not restated here.

This document additionally, and uniquely, prohibits the following token
custody practices, which are specific to credential/token handling rather
than to Gate A2's inspection boundary:

- token value logging,
- token fixture capture,
- token persistence anywhere inside the repository,
- token inclusion in audit receipts,
- copying SDK token storage into project directories.

A Gate B authorization may not be issued until Gate A2 records an explicit
`PASS` per the scope doctrine. The approved external location must be
configured before any Gate B client construction. Its pre-bootstrap state
and the repository's absence of token storage must be witnessed without
reading token values.

The controlled bootstrap witness's post-bootstrap determinations (token
storage touched, expiration/refresh behavior, cleanup/revocation status)
are the same closed set of fields defined in the scope doctrine's Gate B
"witness may capture only" list; no additional determination is required
or permitted beyond that list.

Until witnessed, token status is `token-state-unproven`. Gate A2's own
outcome is reported using the operational status labels
`token-custody-preflight-passed` or `token-custody-preflight-held`, as
defined in the scope doctrine's gate-verdict section; these labels
describe observed state and do not themselves substitute for the `PASS` /
`HOLD` gate verdict.

## 5. Configuration retrieval and bootstrap

The `ClientInitializer` classification, its remote-configuration-retrieval
and token-storage-activation behavior, and the classification of bootstrap
as a potentially networked and token-active event (not inert local
initialization) are defined once, authoritatively, in
`doctrine/SELFBULL-004-SCOPE.md` §9 ("SDK law"). That classification
governs custody consequences as well; it is not restated here.

Within the broader bootstrap receipt defined by the scope doctrine, the
configuration-retrieval field may be represented only as observed `yes`,
`no`, or `unknown`. This restriction applies to that field's representation,
not to the other allowlisted receipt fields. The receipt may not retain raw
remote configuration, raw headers, credentials, tokens, or account-linked
data.

## 6. Plane separation

Until proven otherwise, treat the following as independent custody planes:

- Webull CLI authentication
- Local MCP authentication
- Python SDK authentication

Success in one plane does not prove bootstrap state or authority in the
others.

## 7. Failure handling

If a command or client returns data that appears to contain secrets or
identity-bearing metadata:

1. stop,
2. keep the raw artifact local and ephemeral,
3. do not commit it,
4. scrub only into a reviewed derivative,
5. report the exposure boundary without reproducing the secret.

## 8. Fixture boundary

Raw credential-bearing or identity-bearing output is never a fixture by
default.

Only a scrubbed derivative that has passed:

- secret scan,
- identity scan,
- unstable-field classification,
- human review,
- SHA-256 registration

may become a committed fixture later.
