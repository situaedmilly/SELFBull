"""Fail-closed one-tool composition over the official Webull MCP server.

The composition layer keeps the official server factory as the authority
source, then prunes the discovery surface to exactly one tool:
`get_stock_snapshot`.

This module deliberately avoids import-time side effects. The official
Webull MCP package is imported lazily so the repository can be tested
offline with doubles.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
from dataclasses import dataclass
from typing import Any, Callable

SCHEMA_VERSION = "004B.mcp-one-tool-composition.v1"
SNAPSHOT_TOOL_NAME = "get_stock_snapshot"
DISCOVERY_ALLOWLIST = frozenset({SNAPSHOT_TOOL_NAME})
INVOCATION_ALLOWLIST = frozenset({SNAPSHOT_TOOL_NAME})


class CompositionError(RuntimeError):
    """Raised when the visible MCP surface is not exactly the snapshot tool."""


@dataclass(frozen=True)
class CompositionReceipt:
    schema_version: str
    visible_tool_names: tuple[str, ...]
    discovery_allowlist: frozenset[str]
    invocation_allowlist: frozenset[str]
    forbidden_visible_tool_names: tuple[str, ...]
    exact_surface_match: bool
    mcp_authenticated: bool
    mcp_server_started: bool
    broker_request_count: int
    sdk_called: bool
    execution_authority: bool
    verdict: str


def _resolve(value: Any) -> Any:
    """Resolve awaitables in a synchronous context."""

    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def _tool_name(tool: Any) -> str:
    name = getattr(tool, "name", None)
    if not isinstance(name, str) or not name.strip():
        raise CompositionError("Malformed tool inventory")
    return name.strip()


def _tool_names(server: Any) -> tuple[str, ...]:
    if not hasattr(server, "list_tools"):
        raise CompositionError("Server does not expose list_tools()")

    tools = _resolve(server.list_tools())
    if tools is None:
        return ()

    names = tuple(_tool_name(tool) for tool in tools)
    if len(set(names)) != len(names):
        raise CompositionError("Duplicate tool names detected")
    return names


async def _tool_names_async(server: Any) -> tuple[str, ...]:
    if not hasattr(server, "list_tools"):
        raise CompositionError("Server does not expose list_tools()")

    tools = server.list_tools()
    if inspect.isawaitable(tools):
        tools = await tools
    if tools is None:
        return ()

    names = tuple(_tool_name(tool) for tool in tools)
    if len(set(names)) != len(names):
        raise CompositionError("Duplicate tool names detected")
    return names


def _validate_names(names: tuple[str, ...]) -> CompositionReceipt:
    visible = tuple(sorted(names))
    forbidden = tuple(sorted(name for name in visible if name not in DISCOVERY_ALLOWLIST))
    exact_surface_match = set(visible) == DISCOVERY_ALLOWLIST and not forbidden
    verdict = "SEALED" if exact_surface_match else "BLOCKED"
    return CompositionReceipt(
        schema_version=SCHEMA_VERSION,
        visible_tool_names=visible,
        discovery_allowlist=DISCOVERY_ALLOWLIST,
        invocation_allowlist=INVOCATION_ALLOWLIST,
        forbidden_visible_tool_names=forbidden,
        exact_surface_match=exact_surface_match,
        mcp_authenticated=False,
        mcp_server_started=False,
        broker_request_count=0,
        sdk_called=False,
        execution_authority=False,
        verdict=verdict,
    )


def validate_snapshot_only_surface(server: Any) -> CompositionReceipt:
    """Inspect a server-like object and return a safe composition receipt."""

    target = getattr(server, "_server", server)
    return _validate_names(_tool_names(target))


def _remove_forbidden_tools(server: Any, names: tuple[str, ...]) -> None:
    remover = getattr(server, "remove_tool", None)
    if remover is None:
        if set(names) != DISCOVERY_ALLOWLIST:
            raise CompositionError("Server does not support tool removal")
        return

    for name in names:
        if name not in DISCOVERY_ALLOWLIST:
            remover(name)


def _load_official_build_server() -> Callable[[Any], Any]:
    module = importlib.import_module("webull_openapi_mcp.server")
    build_server = getattr(module, "build_server", None)
    if not callable(build_server):
        raise CompositionError("Official Webull MCP build_server() is unavailable")
    return build_server


def _load_official_config() -> Any:
    module = importlib.import_module("webull_openapi_mcp.config")
    load_config = getattr(module, "load_config", None)
    if not callable(load_config):
        raise CompositionError("Official Webull MCP load_config() is unavailable")
    return load_config()


@dataclass(frozen=True)
class SnapshotOnlyServer:
    """Read-only facade over the pruned official MCP server."""

    _server: Any
    receipt: CompositionReceipt

    async def list_tools(self) -> tuple[str, ...]:
        receipt = _validate_names(await _tool_names_async(self._server))
        if not receipt.exact_surface_match:
            raise CompositionError("Snapshot-only surface drift detected")
        return receipt.visible_tool_names

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        receipt = _validate_names(await _tool_names_async(self._server))
        if not receipt.exact_surface_match:
            raise CompositionError("Snapshot-only surface drift detected")
        if name not in INVOCATION_ALLOWLIST:
            raise CompositionError(f"Tool not allowed: {name}")
        if not hasattr(self._server, "call_tool"):
            raise CompositionError("Server does not expose call_tool()")
        result = self._server.call_tool(name, arguments)
        if inspect.isawaitable(result):
            return await result
        return result


def build_snapshot_only_server(
    config: Any | None = None,
    *,
    build_server_fn: Callable[[Any], Any] | None = None,
    load_config_fn: Callable[[], Any] | None = None,
) -> SnapshotOnlyServer:
    """Build the official server, prune it to one tool, and seal it."""

    build_server = build_server_fn or _load_official_build_server()
    if config is None:
        config = (load_config_fn or _load_official_config)()

    server = build_server(config)
    initial_names = _tool_names(server)
    _remove_forbidden_tools(server, initial_names)

    receipt = validate_snapshot_only_surface(server)
    if not receipt.exact_surface_match:
        raise CompositionError("Snapshot-only surface validation failed")

    return SnapshotOnlyServer(_server=server, receipt=receipt)
