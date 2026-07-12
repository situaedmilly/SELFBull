# SELFBULL-004B MCP Composition Human Decision

## Decision

Authorized: the offline one-tool MCP composition boundary may be manifested
after the inventory instrument seal.

## Why

The official Webull MCP package exposes watchlist and other forbidden surfaces
inside the broader market-data category.  A custom SELFBULL composition layer
is therefore required to keep the discoverable and invokable surface to exactly
`get_stock_snapshot`.

## Boundaries accepted

- Inventory instrument already sealed and merged.
- Composition is offline only in this phase.
- Live MCP authentication remains prohibited.
- Live broker requests remain prohibited.
- SDK transport remains prohibited.

## Human approval

This decision only authorizes the custom composition build and its offline
verification.  It does not authorize a live SPY witness.
