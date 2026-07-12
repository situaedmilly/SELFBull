# SELFBULL-004B MCP Composition Scope

## Purpose

Define the offline SELFBULL-004B composition boundary after the inventory
instrument is sealed and merged.

This scope governs only the custom one-tool MCP composition layer that sits
between the official Webull MCP package and any future live witness gate.

## What this phase does

- Starts from the official `build_server()` surface.
- Treats the official package as the upstream authority for tool registration.
- Prunes the visible surface to exactly one tool:
  `get_stock_snapshot`.
- Rejects any surface drift, duplicate tool names, malformed tool names, or
  newly visible upstream tools.
- Preserves `execution_authority = false`.
- Preserves `mcp_authenticated = false`.
- Preserves `mcp_server_started = false`.
- Preserves `broker_request_count = 0`.
- Preserves `sdk_called = false`.

## What this phase does not do

- It does not authenticate to Webull MCP.
- It does not start a live MCP server.
- It does not invoke any broker tool.
- It does not call the Webull SDK transport.
- It does not create fixtures.
- It does not authorize account, watchlist, trading, position, order,
  screener, event, crypto, futures, polling, or streaming surfaces.
- It does not become the canonical transport layer.  That remains a later
  SELFBULL phase.

## Authority law

Discovery and invocation are both allowlisted to the same single tool:

```text
DISCOVERY_ALLOWLIST = frozenset({"get_stock_snapshot"})
INVOCATION_ALLOWLIST = frozenset({"get_stock_snapshot"})
```

No prompt instruction, environment variable, or upstream default may broaden
that allowlist.

## Refusal conditions

Return `HOLD` or raise a controlled composition error when:

- the visible tool set is not exactly one tool,
- a forbidden tool remains visible,
- a malformed or duplicate tool name appears,
- the server does not support safe pruning,
- the surface changes after validation.

## Rollback

Remove the composition module, its tests, and this doctrine set if the phase is
rescinded.
