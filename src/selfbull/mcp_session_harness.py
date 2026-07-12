"""Reusable in-memory MCP session harness.

The harness is intentionally transport-focused and keeps all Webull-specific
state out of the module boundary. It can run against a fictional FastMCP-like
test double or against the sealed Webull composition when the caller supplies
the matching lifecycle adapter.
"""

from __future__ import annotations

import asyncio
import importlib
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import timedelta
from types import MappingProxyType
from typing import Any, Callable, Mapping, Optional, Tuple

SCHEMA_VERSION = "004B.mcp-session-harness.v2"

ALLOWED_FAILURE_CLASSES = frozenset(
    {
        "NONE",
        "LIFESPAN_START_FAILED",
        "SERVER_RESOLUTION_FAILED",
        "CLIENT_SESSION_START_FAILED",
        "CLIENT_INITIALIZATION_FAILED",
        "DISCOVERY_FAILED",
        "SURFACE_MISMATCH",
        "TOOL_NOT_ALLOWED",
        "INVOCATION_FAILED",
        "TIMEOUT",
        "SHUTDOWN_FAILED",
        "UNEXPECTED_ERROR",
    }
)


@dataclass(frozen=True)
class MCPInvocation:
    tool_name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))


@dataclass(frozen=True)
class MCPSessionReceipt:
    schema_version: str
    initialized: bool
    visible_tool_names: Tuple[str, ...]
    exact_surface_match: bool
    invocation_requested: bool
    invoked_tool_name: Optional[str]
    invocation_completed: bool
    invocation_result_type: Optional[str]
    timeout: bool
    failure_class: str
    client_closed: bool
    server_closed: bool
    broker_request_count: int
    execution_authority: bool


@dataclass(frozen=True)
class MCPLifecycleAdapter:
    lifespan_context_factory: Callable[[Any], Any]
    low_level_server_resolver: Callable[[Any], Any]
    connected_session_factory: Callable[[Any, float], Any]


def _blank_receipt() -> MCPSessionReceipt:
    return MCPSessionReceipt(
        schema_version=SCHEMA_VERSION,
        initialized=False,
        visible_tool_names=(),
        exact_surface_match=False,
        invocation_requested=False,
        invoked_tool_name=None,
        invocation_completed=False,
        invocation_result_type=None,
        timeout=False,
        failure_class="NONE",
        client_closed=False,
        server_closed=False,
        broker_request_count=0,
        execution_authority=False,
    )


def _seal_receipt(receipt: MCPSessionReceipt) -> MCPSessionReceipt:
    return MCPSessionReceipt(
        schema_version=receipt.schema_version,
        initialized=receipt.initialized,
        visible_tool_names=receipt.visible_tool_names,
        exact_surface_match=receipt.exact_surface_match,
        invocation_requested=receipt.invocation_requested,
        invoked_tool_name=receipt.invoked_tool_name,
        invocation_completed=receipt.invocation_completed,
        invocation_result_type=receipt.invocation_result_type,
        timeout=receipt.timeout,
        failure_class=receipt.failure_class,
        client_closed=True,
        server_closed=True,
        broker_request_count=receipt.broker_request_count,
        execution_authority=False,
    )


def _unwrap_server(server: Any) -> Any:
    return getattr(server, "_server", server)


def _default_lifespan_context_factory(server: Any) -> Any:
    wrapper = _unwrap_server(server)
    lifespan_manager = getattr(wrapper, "_lifespan_manager", None)
    if not callable(lifespan_manager):
        raise TypeError("Server does not expose _lifespan_manager()")
    return lifespan_manager()


def _default_low_level_server_resolver(server: Any) -> Any:
    wrapper = _unwrap_server(server)
    low_level_server = getattr(wrapper, "_mcp_server", None)
    if low_level_server is None:
        raise TypeError("Server does not expose a low-level MCP server")
    if not hasattr(low_level_server, "run"):
        raise TypeError("Low-level server does not expose run()")
    if not hasattr(low_level_server, "create_initialization_options"):
        raise TypeError("Low-level server does not expose create_initialization_options()")
    return low_level_server


def _load_runtime_modules() -> tuple[Any, Any]:
    memory_module = importlib.import_module("mcp.shared.memory")
    session_module = importlib.import_module("mcp.client.session")
    return memory_module, session_module


def _default_connected_session_factory(low_level_server: Any, timeout_seconds: float) -> Any:
    memory_module, _ = _load_runtime_modules()
    return memory_module.create_connected_server_and_client_session(
        low_level_server,
        read_timeout_seconds=timedelta(seconds=timeout_seconds),
        raise_exceptions=False,
    )


def _default_lifecycle_adapter() -> MCPLifecycleAdapter:
    return MCPLifecycleAdapter(
        lifespan_context_factory=_default_lifespan_context_factory,
        low_level_server_resolver=_default_low_level_server_resolver,
        connected_session_factory=_default_connected_session_factory,
    )


def _extract_tool_names(list_tools_result: Any) -> Tuple[str, ...]:
    tools = getattr(list_tools_result, "tools", list_tools_result)
    if tools is None:
        return ()

    names: list[str] = []
    for tool in tools:
        name = getattr(tool, "name", None)
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Malformed tool inventory")
        normalized = name.strip()
        if normalized in names:
            raise ValueError("Duplicate tool names detected")
        names.append(normalized)
    return tuple(sorted(names))


def _surface_matches(visible: Tuple[str, ...], expected_tool_names: frozenset[str]) -> bool:
    return set(visible) == expected_tool_names and len(visible) == len(expected_tool_names)


def _leaf_exceptions(exc: BaseException) -> tuple[BaseException, ...]:
    if _is_exception_group(exc):
        leaves: list[BaseException] = []
        for child in getattr(exc, "exceptions", ()):
            leaves.extend(_leaf_exceptions(child))
        return tuple(leaves)
    return (exc,)


def _is_exception_group(exc: BaseException) -> bool:
    return hasattr(exc, "exceptions") and isinstance(getattr(exc, "exceptions"), (list, tuple))


def _classify_stage_failure(default_failure_class: str, exc: BaseException | None = None) -> str:
    if exc is not None:
        for leaf in _leaf_exceptions(exc):
            if isinstance(leaf, (TimeoutError, asyncio.TimeoutError)):
                return "TIMEOUT"
    if default_failure_class not in ALLOWED_FAILURE_CLASSES:
        return "UNEXPECTED_ERROR"
    return default_failure_class


def _failure_receipt(
    *,
    failure_class: str,
    invocation_requested: bool,
    invoked_tool_name: Optional[str],
    initialized: bool = False,
    visible_tool_names: Tuple[str, ...] = (),
    exact_surface_match: bool = False,
    invocation_completed: bool = False,
    invocation_result_type: Optional[str] = None,
    timeout: bool = False,
    broker_request_count: int = 0,
) -> MCPSessionReceipt:
    return _seal_receipt(
        MCPSessionReceipt(
            schema_version=SCHEMA_VERSION,
            initialized=initialized,
            visible_tool_names=visible_tool_names,
            exact_surface_match=exact_surface_match,
            invocation_requested=invocation_requested,
            invoked_tool_name=invoked_tool_name,
            invocation_completed=invocation_completed,
            invocation_result_type=invocation_result_type,
            timeout=timeout,
            failure_class=failure_class,
            client_closed=False,
            server_closed=False,
            broker_request_count=broker_request_count,
            execution_authority=False,
        )
    )


async def run_in_memory_mcp_session(
    server: Any,
    *,
    expected_tool_names: frozenset[str],
    invocation: Optional[MCPInvocation] = None,
    timeout_seconds: float = 30.0,
    lifecycle_adapter: Optional[MCPLifecycleAdapter] = None,
) -> MCPSessionReceipt:
    """Run one in-memory MCP session against a FastMCP-like server."""

    adapter = lifecycle_adapter or _default_lifecycle_adapter()
    expected_tool_names = frozenset(expected_tool_names)
    invocation_requested = invocation is not None
    invoked_tool_name = invocation.tool_name if invocation is not None else None

    try:
        lifespan_context = adapter.lifespan_context_factory(server)
    except BaseException as exc:
        return _failure_receipt(
            failure_class=_classify_stage_failure("LIFESPAN_START_FAILED", exc),
            invocation_requested=invocation_requested,
            invoked_tool_name=invoked_tool_name,
        )

    lifespan_entered = False
    try:
        async with lifespan_context:
            lifespan_entered = True

            try:
                low_level_server = adapter.low_level_server_resolver(server)
            except BaseException as exc:
                return _failure_receipt(
                    failure_class=_classify_stage_failure("SERVER_RESOLUTION_FAILED", exc),
                    invocation_requested=invocation_requested,
                    invoked_tool_name=invoked_tool_name,
                )

            try:
                session_context = adapter.connected_session_factory(low_level_server, timeout_seconds)
            except BaseException as exc:
                return _failure_receipt(
                    failure_class=_classify_stage_failure("CLIENT_SESSION_START_FAILED", exc),
                    invocation_requested=invocation_requested,
                    invoked_tool_name=invoked_tool_name,
                )

            session_entered = False
            try:
                async with session_context as session:
                    session_entered = True

                    try:
                        await session.initialize()
                    except BaseException as exc:
                        return _failure_receipt(
                            failure_class=_classify_stage_failure("CLIENT_INITIALIZATION_FAILED", exc),
                            invocation_requested=invocation_requested,
                            invoked_tool_name=invoked_tool_name,
                        )

                    try:
                        tools_result = await session.list_tools()
                    except BaseException as exc:
                        return _failure_receipt(
                            failure_class=_classify_stage_failure("DISCOVERY_FAILED", exc),
                            invocation_requested=invocation_requested,
                            invoked_tool_name=invoked_tool_name,
                            initialized=True,
                        )

                    try:
                        visible_tool_names = _extract_tool_names(tools_result)
                    except BaseException as exc:
                        return _failure_receipt(
                            failure_class=_classify_stage_failure("DISCOVERY_FAILED", exc),
                            invocation_requested=invocation_requested,
                            invoked_tool_name=invoked_tool_name,
                            initialized=True,
                        )

                    exact_surface_match = _surface_matches(visible_tool_names, expected_tool_names)
                    if not exact_surface_match:
                        return _failure_receipt(
                            failure_class="SURFACE_MISMATCH",
                            invocation_requested=invocation_requested,
                            invoked_tool_name=invoked_tool_name,
                            initialized=True,
                            visible_tool_names=visible_tool_names,
                            exact_surface_match=False,
                        )

                    if invocation is not None and invocation.tool_name not in expected_tool_names:
                        return _failure_receipt(
                            failure_class="TOOL_NOT_ALLOWED",
                            invocation_requested=True,
                            invoked_tool_name=invocation.tool_name,
                            initialized=True,
                            visible_tool_names=visible_tool_names,
                            exact_surface_match=True,
                        )

                    if invocation is None:
                        return _failure_receipt(
                            failure_class="NONE",
                            invocation_requested=False,
                            invoked_tool_name=None,
                            initialized=True,
                            visible_tool_names=visible_tool_names,
                            exact_surface_match=True,
                        )

                    try:
                        result = await asyncio.wait_for(
                            session.call_tool(invocation.tool_name, dict(invocation.arguments)),
                            timeout=timeout_seconds,
                        )
                    except asyncio.TimeoutError as exc:
                        return _failure_receipt(
                            failure_class=_classify_stage_failure("TIMEOUT", exc),
                            invocation_requested=True,
                            invoked_tool_name=invocation.tool_name,
                            initialized=True,
                            visible_tool_names=visible_tool_names,
                            exact_surface_match=True,
                            timeout=True,
                            broker_request_count=1,
                        )
                    except BaseException as exc:
                        return _failure_receipt(
                            failure_class=_classify_stage_failure("INVOCATION_FAILED", exc),
                            invocation_requested=True,
                            invoked_tool_name=invocation.tool_name,
                            initialized=True,
                            visible_tool_names=visible_tool_names,
                            exact_surface_match=True,
                            broker_request_count=1,
                        )

                    return _failure_receipt(
                        failure_class="NONE",
                        invocation_requested=True,
                        invoked_tool_name=invocation.tool_name,
                        initialized=True,
                        visible_tool_names=visible_tool_names,
                        exact_surface_match=True,
                        invocation_completed=True,
                        invocation_result_type=type(result).__name__,
                        broker_request_count=1,
                    )
            except BaseException as exc:
                failure_class = "SHUTDOWN_FAILED" if session_entered else "CLIENT_SESSION_START_FAILED"
                return _failure_receipt(
                    failure_class=_classify_stage_failure(failure_class, exc),
                    invocation_requested=invocation_requested,
                    invoked_tool_name=invoked_tool_name,
                )
    except BaseException as exc:
        failure_class = "SHUTDOWN_FAILED" if lifespan_entered else "LIFESPAN_START_FAILED"
        return _failure_receipt(
            failure_class=_classify_stage_failure(failure_class, exc),
            invocation_requested=invocation_requested,
            invoked_tool_name=invoked_tool_name,
        )

    return _failure_receipt(
        failure_class="UNEXPECTED_ERROR",
        invocation_requested=invocation_requested,
        invoked_tool_name=invoked_tool_name,
    )
