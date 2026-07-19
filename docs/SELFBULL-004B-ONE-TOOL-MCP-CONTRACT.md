# SELFBULL-004B One-Tool MCP Contract

## Contract summary

The SELFBULL-004B composition layer must expose exactly one discoverable tool
and exactly one invokable tool:

```text
get_stock_snapshot
```

## Exact allowlists

```text
DISCOVERY_ALLOWLIST = frozenset({"get_stock_snapshot"})
INVOCATION_ALLOWLIST = frozenset({"get_stock_snapshot"})
```

## Required behavior

- Build from the official `build_server()` surface.
- Prune all visible tools except `get_stock_snapshot`.
- Refuse startup when the visible set is not exactly one tool.
- Revalidate the surface before every list or call operation.
- Refuse hidden tool discovery.
- Refuse hidden tool invocation.
- Refuse malformed names.
- Refuse duplicate names.
- Refuse environment-driven allowlist broadening.
- Preserve value-free receipt fields only.

## Forbidden surfaces

The composition must not expose:

- account
- watchlist
- trading
- order
- position
- screener
- event
- crypto
- futures
- polling
- streaming

## Authority fields

The receipt must keep the following fields false or zero:

- `mcp_authenticated = false`
- `mcp_server_started = false`
- `broker_request_count = 0`
- `sdk_called = false`
- `execution_authority = false`

## Rollback

Remove the composition modules and doctrine files if the phase is revoked.
