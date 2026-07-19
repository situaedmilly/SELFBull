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
from dataclasses import dataclass, field
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
    if not isinstance(name, str) or not name or name != name.strip():
        raise CompositionError("Malformed tool inventory")
    return name


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


class _LowLevelLifecycleCapability:
    """Minimal low-level capability required by the in-memory MCP harness."""

    __slots__ = ("__run_callable", "__initialization_options_callable")

    def __init__(
        self,
        *,
        run: Callable[..., Any],
        create_initialization_options: Callable[..., Any],
    ) -> None:
        self.__run_callable = run
        self.__initialization_options_callable = create_initialization_options

    def run(self, *args: Any, **kwargs: Any) -> Any:
        return self.__run_callable(*args, **kwargs)

    def create_initialization_options(self, *args: Any, **kwargs: Any) -> Any:
        return self.__initialization_options_callable(*args, **kwargs)


class _LifecycleServerCapability:
    """Lifecycle-only view consumed by the canonical session harness."""

    __slots__ = ("__lifespan_factory", "__low_level_server")

    def __init__(
        self,
        *,
        lifespan_manager: Callable[[], Any],
        low_level_server: _LowLevelLifecycleCapability,
    ) -> None:
        self.__lifespan_factory = lifespan_manager
        self.__low_level_server = low_level_server

    def _lifespan_manager(self) -> Any:
        return self.__lifespan_factory()

    @property
    def _mcp_server(self) -> _LowLevelLifecycleCapability:
        return self.__low_level_server


def _lifecycle_capability(server: Any) -> _LifecycleServerCapability:
    lifespan_manager = getattr(server, "_lifespan_manager", None)
    low_level_server = getattr(server, "_mcp_server", None)
    run = getattr(low_level_server, "run", None)
    create_initialization_options = getattr(
        low_level_server,
        "create_initialization_options",
        None,
    )
    if not callable(lifespan_manager):
        raise CompositionError("Server does not expose a lifecycle manager")
    if not callable(run) or not callable(create_initialization_options):
        raise CompositionError("Server does not expose a bounded low-level lifecycle")
    return _LifecycleServerCapability(
        lifespan_manager=lifespan_manager,
        low_level_server=_LowLevelLifecycleCapability(
            run=run,
            create_initialization_options=create_initialization_options,
        ),
    )


@dataclass(frozen=True)
class SnapshotOnlyServer:
    """Lifecycle-only composition handle for the canonical MCP harness."""

    _server: _LifecycleServerCapability = field(repr=False)
    receipt: CompositionReceipt


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

    return SnapshotOnlyServer(
        _server=_lifecycle_capability(server),
        receipt=receipt,
    )
