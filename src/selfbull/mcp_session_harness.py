"""Reusable in-memory MCP session harness.

The harness is intentionally transport-focused and keeps all Webull-specific
state out of the module boundary. It is designed to run against either a real
FastMCP server or a fictional FastMCP-like double in offline tests.
"""

from __future__ import annotations

import asyncio
import importlib
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from datetime import timedelta
from types import MappingProxyType
from typing import Any, Mapping, Optional, Tuple

SCHEMA_VERSION = "004B.mcp-session-harness.v1"

ALLOWED_FAILURE_CLASSES = frozenset(
    {
        "NONE",
        "LIFESPAN_START_FAILED",
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


def _import_runtime_modules() -> Tuple[Any, Any]:
    memory_module = importlib.import_module("mcp.shared.memory")
    session_module = importlib.import_module("mcp.client.session")
    return memory_module, session_module


def _resolve_server_handles(server: Any) -> Tuple[Any, Any]:
    lifespan_manager = getattr(server, "_lifespan_manager", None)
    if not callable(lifespan_manager):
        raise TypeError("Server does not expose _lifespan_manager()")

    low_level_server = getattr(server, "_mcp_server", server)
    if not hasattr(low_level_server, "run"):
        raise TypeError("Server does not expose a runnable MCP transport")
    if not hasattr(low_level_server, "create_initialization_options"):
        raise TypeError("Server does not expose create_initialization_options()")
    return lifespan_manager, low_level_server


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


async def run_in_memory_mcp_session(
    server: Any,
    *,
    expected_tool_names: frozenset[str],
    invocation: Optional[MCPInvocation] = None,
    timeout_seconds: float = 30.0,
) -> MCPSessionReceipt:
    """Run one in-memory MCP session against a FastMCP-like server.

    The function is fail-closed and returns a categorical receipt instead of
    surfacing raw exceptions.
    """

    expected_tool_names = frozenset(expected_tool_names)
    invocation_requested = invocation is not None
    invoked_tool_name = invocation.tool_name if invocation is not None else None
    base_receipt = _blank_receipt()

    try:
        lifespan_manager, low_level_server = _resolve_server_handles(server)
    except Exception:
        return _seal_receipt(
            MCPSessionReceipt(
                schema_version=base_receipt.schema_version,
                initialized=False,
                visible_tool_names=(),
                exact_surface_match=False,
                invocation_requested=invocation_requested,
                invoked_tool_name=invoked_tool_name,
                invocation_completed=False,
                invocation_result_type=None,
                timeout=False,
                failure_class="LIFESPAN_START_FAILED",
                client_closed=False,
                server_closed=False,
                broker_request_count=0,
                execution_authority=False,
            )
        )

    try:
        memory_module, session_module = _import_runtime_modules()
    except Exception:
        return _seal_receipt(
            MCPSessionReceipt(
                schema_version=base_receipt.schema_version,
                initialized=False,
                visible_tool_names=(),
                exact_surface_match=False,
                invocation_requested=invocation_requested,
                invoked_tool_name=invoked_tool_name,
                invocation_completed=False,
                invocation_result_type=None,
                timeout=False,
                failure_class="CLIENT_SESSION_START_FAILED",
                client_closed=False,
                server_closed=False,
                broker_request_count=0,
                execution_authority=False,
            )
        )

    server_task: Optional[asyncio.Task[Any]] = None

    try:
        async with lifespan_manager():
            async with memory_module.create_client_server_memory_streams() as (
                client_streams,
                server_streams,
            ):
                client_read, client_write = client_streams
                server_read, server_write = server_streams
                server_task = asyncio.create_task(
                    low_level_server.run(
                        server_read,
                        server_write,
                        low_level_server.create_initialization_options(),
                        raise_exceptions=False,
                    )
                )
                await asyncio.sleep(0)

                try:
                    session = session_module.ClientSession(
                        read_stream=client_read,
                        write_stream=client_write,
                        read_timeout_seconds=timedelta(seconds=timeout_seconds),
                    )
                except Exception:
                    return _seal_receipt(
                        MCPSessionReceipt(
                            schema_version=base_receipt.schema_version,
                            initialized=False,
                            visible_tool_names=(),
                            exact_surface_match=False,
                            invocation_requested=invocation_requested,
                            invoked_tool_name=invoked_tool_name,
                            invocation_completed=False,
                            invocation_result_type=None,
                            timeout=False,
                            failure_class="CLIENT_SESSION_START_FAILED",
                            client_closed=False,
                            server_closed=False,
                            broker_request_count=0,
                            execution_authority=False,
                        )
                    )

                try:
                    await session.initialize()
                except Exception:
                    return _seal_receipt(
                        MCPSessionReceipt(
                            schema_version=base_receipt.schema_version,
                            initialized=False,
                            visible_tool_names=(),
                            exact_surface_match=False,
                            invocation_requested=invocation_requested,
                            invoked_tool_name=invoked_tool_name,
                            invocation_completed=False,
                            invocation_result_type=None,
                            timeout=False,
                            failure_class="CLIENT_INITIALIZATION_FAILED",
                            client_closed=False,
                            server_closed=False,
                            broker_request_count=0,
                            execution_authority=False,
                        )
                    )

                try:
                    tools_result = await session.list_tools()
                except Exception:
                    return _seal_receipt(
                        MCPSessionReceipt(
                            schema_version=base_receipt.schema_version,
                            initialized=True,
                            visible_tool_names=(),
                            exact_surface_match=False,
                            invocation_requested=invocation_requested,
                            invoked_tool_name=invoked_tool_name,
                            invocation_completed=False,
                            invocation_result_type=None,
                            timeout=False,
                            failure_class="DISCOVERY_FAILED",
                            client_closed=False,
                            server_closed=False,
                            broker_request_count=0,
                            execution_authority=False,
                        )
                    )

                visible_tool_names = _extract_tool_names(tools_result)
                exact_surface_match = _surface_matches(visible_tool_names, expected_tool_names)

                if not exact_surface_match:
                    return _seal_receipt(
                        MCPSessionReceipt(
                            schema_version=SCHEMA_VERSION,
                            initialized=True,
                            visible_tool_names=visible_tool_names,
                            exact_surface_match=False,
                            invocation_requested=invocation_requested,
                            invoked_tool_name=invoked_tool_name,
                            invocation_completed=False,
                            invocation_result_type=None,
                            timeout=False,
                            failure_class="SURFACE_MISMATCH",
                            client_closed=False,
                            server_closed=False,
                            broker_request_count=0,
                            execution_authority=False,
                        )
                    )

                if invocation is not None and invocation.tool_name not in expected_tool_names:
                    return _seal_receipt(
                        MCPSessionReceipt(
                            schema_version=SCHEMA_VERSION,
                            initialized=True,
                            visible_tool_names=visible_tool_names,
                            exact_surface_match=True,
                            invocation_requested=True,
                            invoked_tool_name=invocation.tool_name,
                            invocation_completed=False,
                            invocation_result_type=None,
                            timeout=False,
                            failure_class="TOOL_NOT_ALLOWED",
                            client_closed=False,
                            server_closed=False,
                            broker_request_count=0,
                            execution_authority=False,
                        )
                    )

                if invocation is None:
                    return _seal_receipt(
                        MCPSessionReceipt(
                            schema_version=SCHEMA_VERSION,
                            initialized=True,
                            visible_tool_names=visible_tool_names,
                            exact_surface_match=True,
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
                    )

                try:
                    result = await asyncio.wait_for(
                        session.call_tool(invocation.tool_name, dict(invocation.arguments)),
                        timeout=timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    return _seal_receipt(
                        MCPSessionReceipt(
                            schema_version=SCHEMA_VERSION,
                            initialized=True,
                            visible_tool_names=visible_tool_names,
                            exact_surface_match=True,
                            invocation_requested=True,
                            invoked_tool_name=invocation.tool_name,
                            invocation_completed=False,
                            invocation_result_type=None,
                            timeout=True,
                            failure_class="TIMEOUT",
                            client_closed=False,
                            server_closed=False,
                            broker_request_count=1,
                            execution_authority=False,
                        )
                    )
                except Exception:
                    return _seal_receipt(
                        MCPSessionReceipt(
                            schema_version=SCHEMA_VERSION,
                            initialized=True,
                            visible_tool_names=visible_tool_names,
                            exact_surface_match=True,
                            invocation_requested=True,
                            invoked_tool_name=invocation.tool_name,
                            invocation_completed=False,
                            invocation_result_type=None,
                            timeout=False,
                            failure_class="INVOCATION_FAILED",
                            client_closed=False,
                            server_closed=False,
                            broker_request_count=1,
                            execution_authority=False,
                        )
                    )
                else:
                    return _seal_receipt(
                        MCPSessionReceipt(
                            schema_version=SCHEMA_VERSION,
                            initialized=True,
                            visible_tool_names=visible_tool_names,
                            exact_surface_match=True,
                            invocation_requested=True,
                            invoked_tool_name=invocation.tool_name,
                            invocation_completed=True,
                            invocation_result_type=type(result).__name__,
                            timeout=False,
                            failure_class="NONE",
                            client_closed=False,
                            server_closed=False,
                            broker_request_count=1,
                            execution_authority=False,
                        )
                    )
    except Exception:
        return _seal_receipt(
            MCPSessionReceipt(
                schema_version=SCHEMA_VERSION,
                initialized=False,
                visible_tool_names=(),
                exact_surface_match=False,
                invocation_requested=invocation_requested,
                invoked_tool_name=invoked_tool_name,
                invocation_completed=False,
                invocation_result_type=None,
                timeout=False,
                failure_class="LIFESPAN_START_FAILED",
                client_closed=False,
                server_closed=False,
                broker_request_count=0,
                execution_authority=False,
            )
        )
    finally:
        if server_task is not None:
            server_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                try:
                    await asyncio.wait_for(server_task, timeout=max(timeout_seconds, 0.1))
                except asyncio.TimeoutError:
                    pass

    return _seal_receipt(
        MCPSessionReceipt(
            schema_version=SCHEMA_VERSION,
            initialized=False,
            visible_tool_names=(),
            exact_surface_match=False,
            invocation_requested=invocation_requested,
            invoked_tool_name=invoked_tool_name,
            invocation_completed=False,
            invocation_result_type=None,
            timeout=False,
            failure_class="UNEXPECTED_ERROR",
            client_closed=False,
            server_closed=False,
            broker_request_count=0,
            execution_authority=False,
        )
    )
