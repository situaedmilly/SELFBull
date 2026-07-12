# SELFBULL-004 Credential Custody

> Status: custody doctrine for SELFBULL-004A only.
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

## 3. Reporting law

SELFBULL may report only presence / missing state.
Masked previews remain prohibited in SELFBULL-004A.

It must not print:

- credential values,
- token values,
- session cookies,
- refresh tokens,
- bearer strings,
- account-linked identity values.

If a future phase adds a transport receipt, the receipt must remain
redacted and must not disclose secrets.

## 4. Plane separation

Until proven otherwise, treat the following as independent custody planes:

- Webull CLI authentication
- Local MCP authentication
- Python SDK authentication

Successful authentication in one plane does not prove authenticated state
in the others.

## 5. Failure handling

If a command or client returns data that appears to contain secrets or
identity-bearing metadata:

1. stop,
2. keep the raw artifact local and ephemeral,
3. do not commit it,
4. scrub only into a reviewed derivative,
5. report the exposure boundary without reproducing the secret.

## 6. Fixture boundary

Raw credential-bearing or identity-bearing output is never a fixture by
default.

Only a scrubbed derivative that has passed:

- secret scan,
- identity scan,
- unstable-field classification,
- human review,
- SHA-256 registration

may become a committed fixture later.
