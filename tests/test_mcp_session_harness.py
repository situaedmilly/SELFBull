from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from types import MappingProxyType, SimpleNamespace
from typing import Optional
from unittest import IsolatedAsyncioTestCase

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from selfbull.mcp_session_harness import (  # noqa: E402
    MCPInvocation,
    MCPLifecycleAdapter,
    MCPSessionReceipt,
    run_in_memory_mcp_session,
)


def _stock_snapshot_schema():
    return {
        "type": "object",
        "properties": {
            "symbols": {"type": "string"},
            "category": {"type": "string", "default": "US_STOCK"},
            "extend_hour_required": {"type": "boolean", "default": False},
            "overnight_required": {"type": "boolean", "default": False},
        },
        "required": ["symbols"],
    }


@dataclass
class SessionScenario:
    visible_tool_names: list[str] = field(default_factory=lambda: ["fictional_snapshot"])
    tool_schemas: dict[str, dict | None] = field(
        default_factory=lambda: {
            "fictional_snapshot": _stock_snapshot_schema()
        }
    )
    initialize_error: Optional[BaseException] = None
    discovery_error: Optional[BaseException] = None
    invocation_error: Optional[BaseException] = None
    lifespan_error: Optional[BaseException] = None
    lifespan_exit_error: Optional[BaseException] = None
    session_factory_error: Optional[BaseException] = None
    session_enter_error: Optional[BaseException] = None
    session_exit_error: Optional[BaseException] = None
    call_delay: float = 0.0
    events: list[str] = field(default_factory=list)
    call_tool_calls: int = 0
    call_tool_arguments: list[dict] = field(default_factory=list)
    received_low_level_server: object | None = None
    low_level_resolved: bool = False


class SyntheticExceptionGroup(RuntimeError):
    def __init__(self, message: str, exceptions: list[BaseException]) -> None:
        super().__init__(message)
        self.exceptions = exceptions


class FakeLowLevelServer:
    def __init__(self, scenario: SessionScenario) -> None:
        self.scenario = scenario
        self.create_initialization_options_calls = 0

    def create_initialization_options(self) -> object:
        self.create_initialization_options_calls += 1
        return object()

    async def run(self, *args, **kwargs) -> None:  # pragma: no cover - kept as a shape witness
        await asyncio.sleep(0)


class FakeLifespanContext:
    def __init__(self, scenario: SessionScenario) -> None:
        self.scenario = scenario
        self.entered = 0
        self.exited = 0

    async def __aenter__(self):
        self.entered += 1
        self.scenario.events.append("lifespan_enter")
        if self.scenario.lifespan_error is not None:
            raise self.scenario.lifespan_error
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.exited += 1
        self.scenario.events.append("lifespan_exit")
        if self.scenario.lifespan_exit_error is not None:
            raise self.scenario.lifespan_exit_error
        return False


class FakeHighLevelServer:
    def __init__(self, scenario: SessionScenario) -> None:
        self.scenario = scenario
        self._mcp_server = FakeLowLevelServer(scenario)
        self._lifespan = FakeLifespanContext(scenario)

    def _lifespan_manager(self):
        return self._lifespan


class FakeClientSession:
    def __init__(self, scenario: SessionScenario, low_level_server: object) -> None:
        self.scenario = scenario
        self.low_level_server = low_level_server
        self.initialize_calls = 0
        self.list_tools_calls = 0
        self.call_tool_calls = 0
        self.closed = False

    async def initialize(self):
        self.initialize_calls += 1
        self.scenario.events.append("initialize")
        if self.scenario.initialize_error is not None:
            raise self.scenario.initialize_error
        return SimpleNamespace(protocolVersion="fictional")

    async def list_tools(self, cursor=None, *, params=None):
        self.list_tools_calls += 1
        self.scenario.events.append("list_tools")
        if self.scenario.discovery_error is not None:
            raise self.scenario.discovery_error
        tools = [
            SimpleNamespace(name=name, inputSchema=self.scenario.tool_schemas.get(name))
            for name in self.scenario.visible_tool_names
        ]
        return SimpleNamespace(tools=tools)

    async def call_tool(self, name, arguments=None, read_timeout_seconds=None, progress_callback=None, *, meta=None):
        self.call_tool_calls += 1
        self.scenario.call_tool_calls += 1
        self.scenario.call_tool_arguments.append(dict(arguments or {}))
        self.scenario.events.append("call_tool")
        if self.scenario.invocation_error is not None:
            raise self.scenario.invocation_error
        if self.scenario.call_delay:
            await asyncio.sleep(self.scenario.call_delay)
        return {
            "tool": name,
            "arguments": dict(arguments or {}),
            "result": "fictional_snapshot",
        }


class FakeSessionContext:
    def __init__(self, scenario: SessionScenario, low_level_server: object) -> None:
        self.scenario = scenario
        self.low_level_server = low_level_server
        self.client = FakeClientSession(scenario, low_level_server)
        self.entered = 0
        self.exited = 0

    async def __aenter__(self):
        self.entered += 1
        self.scenario.events.append("session_enter")
        if self.scenario.session_enter_error is not None:
            raise self.scenario.session_enter_error
        return self.client

    async def __aexit__(self, exc_type, exc, tb):
        self.exited += 1
        self.scenario.events.append("session_exit")
        self.client.closed = True
        if self.scenario.session_exit_error is not None:
            raise self.scenario.session_exit_error
        return False


def _make_adapter(scenario: SessionScenario, server: FakeHighLevelServer) -> MCPLifecycleAdapter:
    def lifespan_context_factory(seen_server: object):
        assert seen_server is server
        return server._lifespan_manager()

    def low_level_server_resolver(seen_server: object):
        assert seen_server is server
        scenario.low_level_resolved = True
        scenario.events.append("resolve_low_level")
        return server._mcp_server

    def connected_session_factory(low_level_server: object, timeout_seconds: float):
        scenario.received_low_level_server = low_level_server
        scenario.events.append("connected_session_factory")
        if low_level_server is not server._mcp_server:
            raise AssertionError("connected_session_factory received the wrong server")
        if scenario.session_factory_error is not None:
            raise scenario.session_factory_error

        @asynccontextmanager
        async def _session_context():
            context = FakeSessionContext(scenario, low_level_server)
            async with context as client:
                yield client

        return _session_context()

    return MCPLifecycleAdapter(
        lifespan_context_factory=lifespan_context_factory,
        low_level_server_resolver=low_level_server_resolver,
        connected_session_factory=connected_session_factory,
    )


class TestMCPSessionHarness(IsolatedAsyncioTestCase):
    async def _run_schema_case(self, schema, arguments):
        scenario = SessionScenario(
            visible_tool_names=["get_stock_snapshot"],
            tool_schemas={"get_stock_snapshot": schema},
        )
        server = FakeHighLevelServer(scenario)
        receipt = await run_in_memory_mcp_session(
            server,
            expected_tool_names=frozenset({"get_stock_snapshot"}),
            invocation=MCPInvocation("get_stock_snapshot", arguments),
            timeout_seconds=1.0,
            lifecycle_adapter=_make_adapter(scenario, server),
        )
        return receipt, scenario

    async def test_fictional_harness_runs_successfully_offline(self):
        scenario = SessionScenario()
        server = FakeHighLevelServer(scenario)
        adapter = _make_adapter(scenario, server)

        receipt = await run_in_memory_mcp_session(
            server,
            expected_tool_names=frozenset({"fictional_snapshot"}),
            invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
            timeout_seconds=1.0,
            lifecycle_adapter=adapter,
        )

        self.assertIsInstance(receipt, MCPSessionReceipt)
        self.assertEqual(receipt.schema_version, "004B.mcp-session-harness.v2")
        self.assertTrue(receipt.initialized)
        self.assertEqual(receipt.visible_tool_names, ("fictional_snapshot",))
        self.assertTrue(receipt.exact_surface_match)
        self.assertTrue(receipt.invocation_requested)
        self.assertEqual(receipt.invoked_tool_name, "fictional_snapshot")
        self.assertTrue(receipt.invocation_completed)
        self.assertEqual(receipt.invocation_result_type, "dict")
        self.assertFalse(receipt.timeout)
        self.assertEqual(receipt.failure_class, "NONE")
        self.assertTrue(receipt.client_closed)
        self.assertTrue(receipt.server_closed)
        self.assertEqual(receipt.broker_request_count, 1)
        self.assertFalse(receipt.execution_authority)
        self.assertEqual(scenario.events, [
            "lifespan_enter",
            "resolve_low_level",
            "connected_session_factory",
            "session_enter",
            "initialize",
            "list_tools",
            "call_tool",
            "session_exit",
            "lifespan_exit",
        ])
        self.assertIs(scenario.received_low_level_server, server._mcp_server)
        self.assertTrue(scenario.low_level_resolved)

    async def test_schema_admission_maps_canonical_symbol_to_live_symbols_string(self):
        scenario = SessionScenario(
            visible_tool_names=["get_stock_snapshot"],
            tool_schemas={
                "get_stock_snapshot": _stock_snapshot_schema()
            },
        )
        server = FakeHighLevelServer(scenario)
        adapter = _make_adapter(scenario, server)

        arguments = {"symbol": "SPY"}
        receipt = await run_in_memory_mcp_session(
            server,
            expected_tool_names=frozenset({"get_stock_snapshot"}),
            invocation=MCPInvocation("get_stock_snapshot", arguments),
            timeout_seconds=1.0,
            lifecycle_adapter=adapter,
        )

        self.assertEqual(receipt.failure_class, "NONE")
        self.assertTrue(receipt.invocation_completed)
        self.assertEqual(scenario.call_tool_arguments, [{"symbols": "SPY"}])
        self.assertEqual(arguments, {"symbol": "SPY"})

    async def test_schema_admission_refuses_malformed_schemas_without_call(self):
        malformed = [
            None,
            [],
            "schema",
            {"type": "object"},
            {"type": "object", "properties": []},
            {"type": "object", "properties": {}},
            {"type": "object", "properties": {"symbols": []}},
            {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    **_stock_snapshot_schema()["properties"],
                },
                "required": ["symbols"],
            },
            {
                **_stock_snapshot_schema(),
                "properties": {
                    **_stock_snapshot_schema()["properties"],
                    "symbols": {"type": "array", "items": {"type": "string"}},
                },
            },
            {
                **_stock_snapshot_schema(),
                "properties": {
                    **_stock_snapshot_schema()["properties"],
                    "category": {"type": "string", "default": "CRYPTO"},
                },
            },
            {
                **_stock_snapshot_schema(),
                "properties": {
                    **_stock_snapshot_schema()["properties"],
                    "extend_hour_required": {"type": "boolean", "default": True},
                },
            },
            {
                **_stock_snapshot_schema(),
                "properties": {
                    **_stock_snapshot_schema()["properties"],
                    "overnight_required": {"type": "string", "default": False},
                },
            },
            {
                "type": "object",
                "properties": {"symbols": {"type": "string"}},
                "required": ["symbols"],
            },
            {
                **_stock_snapshot_schema(),
                "required": [],
            },
            {
                **_stock_snapshot_schema(),
                "required": "symbols",
            },
            {
                **_stock_snapshot_schema(),
                "required": ["symbols", "unsupported"],
            },
        ]
        for schema in malformed:
            with self.subTest(schema=schema):
                receipt, scenario = await self._run_schema_case(schema, {"symbol": "SPY"})
                self.assertEqual(receipt.failure_class, "SCHEMA_ADMISSION_FAILED")
                self.assertEqual(scenario.call_tool_calls, 0)
                self.assertFalse(receipt.execution_authority)

    async def test_schema_admission_refuses_ambiguous_and_invalid_inputs(self):
        schema = _stock_snapshot_schema()
        invalid_arguments = [
            {"symbol": "SPY", "symbols": ["SPY"]},
            {"symbols": ["SPY"]},
            {"symbol": "SPY", "extra": True},
            {"symbol": "SPY", "category": "US_STOCK"},
            {"symbol": "SPY", "extend_hour_required": False},
            {"symbol": "SPY", "overnight_required": False},
            {},
            {"symbol": ""},
            {"symbol": "   "},
            {"symbol": None},
            {"symbol": ["SPY"]},
            {"symbol": 123},
            {"symbol": True},
        ]
        for arguments in invalid_arguments:
            with self.subTest(arguments=arguments):
                receipt, scenario = await self._run_schema_case(schema, arguments)
                self.assertEqual(receipt.failure_class, "SCHEMA_ADMISSION_FAILED")
                self.assertEqual(scenario.call_tool_calls, 0)
                self.assertFalse(receipt.execution_authority)

    async def test_forbidden_invocation_is_refused_before_handler_lookup(self):
        scenario = SessionScenario()
        server = FakeHighLevelServer(scenario)
        adapter = _make_adapter(scenario, server)

        receipt = await run_in_memory_mcp_session(
            server,
            expected_tool_names=frozenset({"fictional_snapshot"}),
            invocation=MCPInvocation("fictional_mutation", {"name": "Tech Stocks"}),
            timeout_seconds=1.0,
            lifecycle_adapter=adapter,
        )

        self.assertEqual(receipt.failure_class, "TOOL_NOT_ALLOWED")
        self.assertTrue(receipt.invocation_requested)
        self.assertEqual(receipt.invoked_tool_name, "fictional_mutation")
        self.assertFalse(receipt.invocation_completed)
        self.assertEqual(receipt.broker_request_count, 0)
        self.assertEqual(scenario.events, [
            "lifespan_enter",
            "resolve_low_level",
            "connected_session_factory",
            "session_enter",
            "initialize",
            "list_tools",
            "session_exit",
            "lifespan_exit",
        ])
        self.assertEqual(server._mcp_server.create_initialization_options_calls, 0)

    async def test_surface_mismatch_blocks_invocation(self):
        scenario = SessionScenario(visible_tool_names=["fictional_snapshot", "fictional_mutation"])
        server = FakeHighLevelServer(scenario)
        adapter = _make_adapter(scenario, server)

        receipt = await run_in_memory_mcp_session(
            server,
            expected_tool_names=frozenset({"fictional_snapshot"}),
            invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
            timeout_seconds=1.0,
            lifecycle_adapter=adapter,
        )

        self.assertEqual(receipt.failure_class, "SURFACE_MISMATCH")
        self.assertFalse(receipt.invocation_completed)
        self.assertEqual(receipt.broker_request_count, 0)
        self.assertEqual(receipt.visible_tool_names, ("fictional_mutation", "fictional_snapshot"))
        self.assertTrue(receipt.client_closed)
        self.assertTrue(receipt.server_closed)
        self.assertNotIn("call_tool", scenario.events)

    async def test_discovery_rejects_edge_whitespace_without_normalizing_names(self):
        malformed_names = (
            " fictional_snapshot",
            "fictional_snapshot ",
            "\u00a0fictional_snapshot",
            "fictional_snapshot\u00a0",
        )
        for tool_name in malformed_names:
            with self.subTest(tool_name=repr(tool_name)):
                scenario = SessionScenario(
                    visible_tool_names=[tool_name],
                    tool_schemas={tool_name: _stock_snapshot_schema()},
                )
                server = FakeHighLevelServer(scenario)

                receipt = await run_in_memory_mcp_session(
                    server,
                    expected_tool_names=frozenset({"fictional_snapshot"}),
                    timeout_seconds=1.0,
                    lifecycle_adapter=_make_adapter(scenario, server),
                )

                self.assertEqual(receipt.failure_class, "DISCOVERY_FAILED")
                self.assertEqual(receipt.visible_tool_names, ())
                self.assertEqual(scenario.call_tool_calls, 0)
                self.assertTrue(receipt.client_closed)
                self.assertTrue(receipt.server_closed)

    async def test_timeout_becomes_controlled(self):
        scenario = SessionScenario(call_delay=0.1)
        server = FakeHighLevelServer(scenario)
        adapter = _make_adapter(scenario, server)

        receipt = await run_in_memory_mcp_session(
            server,
            expected_tool_names=frozenset({"fictional_snapshot"}),
            invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
            timeout_seconds=0.001,
            lifecycle_adapter=adapter,
        )

        self.assertEqual(receipt.failure_class, "TIMEOUT")
        self.assertTrue(receipt.timeout)
        self.assertFalse(receipt.invocation_completed)
        self.assertEqual(receipt.broker_request_count, 1)
        self.assertTrue(receipt.client_closed)
        self.assertTrue(receipt.server_closed)

    async def test_tool_exception_becomes_controlled(self):
        scenario = SessionScenario(invocation_error=ValueError("boom"))
        server = FakeHighLevelServer(scenario)
        adapter = _make_adapter(scenario, server)

        receipt = await run_in_memory_mcp_session(
            server,
            expected_tool_names=frozenset({"fictional_snapshot"}),
            invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
            timeout_seconds=1.0,
            lifecycle_adapter=adapter,
        )

        self.assertEqual(receipt.failure_class, "INVOCATION_FAILED")
        self.assertFalse(receipt.invocation_completed)
        self.assertEqual(receipt.broker_request_count, 1)
        self.assertTrue(receipt.client_closed)
        self.assertTrue(receipt.server_closed)

    async def test_initialization_failure_becomes_controlled(self):
        scenario = SessionScenario(initialize_error=RuntimeError("init failed"))
        server = FakeHighLevelServer(scenario)
        adapter = _make_adapter(scenario, server)

        receipt = await run_in_memory_mcp_session(
            server,
            expected_tool_names=frozenset({"fictional_snapshot"}),
            invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
            timeout_seconds=1.0,
            lifecycle_adapter=adapter,
        )

        self.assertEqual(receipt.failure_class, "CLIENT_INITIALIZATION_FAILED")
        self.assertFalse(receipt.initialized)
        self.assertTrue(receipt.client_closed)
        self.assertTrue(receipt.server_closed)
        self.assertEqual(receipt.broker_request_count, 0)

    async def test_exception_group_is_classified_stably(self):
        scenario = SessionScenario(initialize_error=SyntheticExceptionGroup("init", [RuntimeError("boom")]))
        server = FakeHighLevelServer(scenario)
        adapter = _make_adapter(scenario, server)

        receipt = await run_in_memory_mcp_session(
            server,
            expected_tool_names=frozenset({"fictional_snapshot"}),
            invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
            timeout_seconds=1.0,
            lifecycle_adapter=adapter,
        )

        self.assertEqual(receipt.failure_class, "CLIENT_INITIALIZATION_FAILED")
        self.assertTrue(receipt.client_closed)
        self.assertTrue(receipt.server_closed)

    async def test_lifespan_failure_becomes_controlled(self):
        scenario = SessionScenario(lifespan_error=RuntimeError("lifespan failed"))
        server = FakeHighLevelServer(scenario)
        adapter = _make_adapter(scenario, server)

        receipt = await run_in_memory_mcp_session(
            server,
            expected_tool_names=frozenset({"fictional_snapshot"}),
            invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
            timeout_seconds=1.0,
            lifecycle_adapter=adapter,
        )

        self.assertEqual(receipt.failure_class, "LIFESPAN_START_FAILED")
        self.assertFalse(receipt.initialized)
        self.assertFalse(receipt.client_closed)
        self.assertFalse(receipt.server_closed)
        self.assertEqual(server._lifespan.entered, 1)
        self.assertEqual(server._lifespan.exited, 0)
        self.assertEqual(scenario.events, ["lifespan_enter"])

    async def test_lifespan_shutdown_failure_is_controlled(self):
        scenario = SessionScenario(lifespan_exit_error=RuntimeError("lifespan shutdown failed"))
        server = FakeHighLevelServer(scenario)
        adapter = _make_adapter(scenario, server)

        receipt = await run_in_memory_mcp_session(
            server,
            expected_tool_names=frozenset({"fictional_snapshot"}),
            invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
            timeout_seconds=1.0,
            lifecycle_adapter=adapter,
        )

        self.assertEqual(receipt.failure_class, "SHUTDOWN_FAILED")
        self.assertTrue(receipt.client_closed)
        self.assertFalse(receipt.server_closed)
        self.assertEqual(server._lifespan.entered, 1)
        self.assertEqual(server._lifespan.exited, 1)
        self.assertEqual(scenario.events[-2:], ["session_exit", "lifespan_exit"])

    async def test_low_level_resolution_failure_becomes_controlled(self):
        scenario = SessionScenario()
        server = FakeHighLevelServer(scenario)

        def lifespan_context_factory(seen_server: object):
            assert seen_server is server
            return server._lifespan_manager()

        def low_level_server_resolver(seen_server: object):
            assert seen_server is server
            raise RuntimeError("no low-level server")

        def connected_session_factory(low_level_server: object, timeout_seconds: float):
            raise AssertionError("should not be reached")

        adapter = MCPLifecycleAdapter(
            lifespan_context_factory=lifespan_context_factory,
            low_level_server_resolver=low_level_server_resolver,
            connected_session_factory=connected_session_factory,
        )

        receipt = await run_in_memory_mcp_session(
            server,
            expected_tool_names=frozenset({"fictional_snapshot"}),
            invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
            timeout_seconds=1.0,
            lifecycle_adapter=adapter,
        )

        self.assertEqual(receipt.failure_class, "SERVER_RESOLUTION_FAILED")
        self.assertFalse(receipt.client_closed)
        self.assertFalse(receipt.server_closed)
        self.assertFalse(receipt.execution_authority)

    async def test_shutdown_failure_is_controlled(self):
        scenario = SessionScenario(session_exit_error=RuntimeError("shutdown failed"))
        server = FakeHighLevelServer(scenario)
        adapter = _make_adapter(scenario, server)

        receipt = await run_in_memory_mcp_session(
            server,
            expected_tool_names=frozenset({"fictional_snapshot"}),
            invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
            timeout_seconds=1.0,
            lifecycle_adapter=adapter,
        )

        self.assertEqual(receipt.failure_class, "SHUTDOWN_FAILED")
        self.assertFalse(receipt.client_closed)
        self.assertFalse(receipt.server_closed)
        self.assertFalse(receipt.execution_authority)
        pending = [
            task
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task() and not task.done()
        ]
        self.assertEqual(pending, [])

    async def test_dual_shutdown_failure_reports_neither_layer_closed(self):
        scenario = SessionScenario(
            session_exit_error=RuntimeError("session shutdown failed"),
            lifespan_exit_error=RuntimeError("lifespan shutdown failed"),
        )
        server = FakeHighLevelServer(scenario)

        receipt = await run_in_memory_mcp_session(
            server,
            expected_tool_names=frozenset({"fictional_snapshot"}),
            invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
            timeout_seconds=1.0,
            lifecycle_adapter=_make_adapter(scenario, server),
        )

        self.assertEqual(receipt.failure_class, "SHUTDOWN_FAILED")
        self.assertFalse(receipt.client_closed)
        self.assertFalse(receipt.server_closed)
        self.assertFalse(receipt.execution_authority)
        self.assertEqual(scenario.events[-2:], ["session_exit", "lifespan_exit"])
        pending = [
            task
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task() and not task.done()
        ]
        self.assertEqual(pending, [])

    async def test_session_entry_failure_reports_only_confirmed_server_closure(self):
        scenario = SessionScenario(session_enter_error=RuntimeError("session start failed"))
        server = FakeHighLevelServer(scenario)

        receipt = await run_in_memory_mcp_session(
            server,
            expected_tool_names=frozenset({"fictional_snapshot"}),
            invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
            timeout_seconds=1.0,
            lifecycle_adapter=_make_adapter(scenario, server),
        )

        self.assertEqual(receipt.failure_class, "CLIENT_SESSION_START_FAILED")
        self.assertFalse(receipt.client_closed)
        self.assertFalse(receipt.server_closed)
        self.assertFalse(receipt.execution_authority)
        self.assertEqual(scenario.events[-1], "lifespan_exit")

    async def test_cancelled_error_propagates_from_every_async_boundary(self):
        scenarios = (
            SessionScenario(lifespan_error=asyncio.CancelledError()),
            SessionScenario(session_enter_error=asyncio.CancelledError()),
            SessionScenario(initialize_error=asyncio.CancelledError()),
            SessionScenario(discovery_error=asyncio.CancelledError()),
            SessionScenario(invocation_error=asyncio.CancelledError()),
            SessionScenario(session_exit_error=asyncio.CancelledError()),
            SessionScenario(lifespan_exit_error=asyncio.CancelledError()),
        )
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                server = FakeHighLevelServer(scenario)
                with self.assertRaises(asyncio.CancelledError):
                    await run_in_memory_mcp_session(
                        server,
                        expected_tool_names=frozenset({"fictional_snapshot"}),
                        invocation=MCPInvocation(
                            "fictional_snapshot", {"symbol": "SPY"}
                        ),
                        timeout_seconds=1.0,
                        lifecycle_adapter=_make_adapter(scenario, server),
                    )

                pending = [
                    task
                    for task in asyncio.all_tasks()
                    if task is not asyncio.current_task() and not task.done()
                ]
                self.assertEqual(pending, [])

    async def test_cancellation_survives_session_cleanup_failure(self):
        scenario = SessionScenario(
            invocation_error=asyncio.CancelledError(),
            session_exit_error=RuntimeError("session cleanup failed"),
        )
        server = FakeHighLevelServer(scenario)

        with self.assertRaises(asyncio.CancelledError) as caught:
            await run_in_memory_mcp_session(
                server,
                expected_tool_names=frozenset({"fictional_snapshot"}),
                invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
                timeout_seconds=1.0,
                lifecycle_adapter=_make_adapter(scenario, server),
            )

        self.assertEqual(scenario.call_tool_calls, 1)
        self.assertEqual(caught.exception.args, ())
        self.assertIsNone(caught.exception.__cause__)
        self.assertIsNone(caught.exception.__context__)
        self.assertEqual(scenario.events[-2:], ["session_exit", "lifespan_exit"])
        pending = [
            task
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task() and not task.done()
        ]
        self.assertEqual(pending, [])

    async def test_cancellation_survives_lifespan_cleanup_failure(self):
        scenario = SessionScenario(
            invocation_error=asyncio.CancelledError(),
            lifespan_exit_error=RuntimeError("lifespan cleanup failed"),
        )
        server = FakeHighLevelServer(scenario)

        with self.assertRaises(asyncio.CancelledError) as caught:
            await run_in_memory_mcp_session(
                server,
                expected_tool_names=frozenset({"fictional_snapshot"}),
                invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
                timeout_seconds=1.0,
                lifecycle_adapter=_make_adapter(scenario, server),
            )

        self.assertEqual(scenario.call_tool_calls, 1)
        self.assertEqual(caught.exception.args, ())
        self.assertIsNone(caught.exception.__cause__)
        self.assertIsNone(caught.exception.__context__)
        self.assertEqual(scenario.events[-2:], ["session_exit", "lifespan_exit"])
        pending = [
            task
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task() and not task.done()
        ]
        self.assertEqual(pending, [])

    async def test_stale_cancellation_chain_does_not_manufacture_cancellation(self):
        cleanup_errors = []
        for relationship in ("__cause__", "__context__"):
            cleanup_error = RuntimeError("stale cleanup detail")
            setattr(cleanup_error, relationship, asyncio.CancelledError())
            cleanup_errors.append(cleanup_error)

        for cleanup_error in cleanup_errors:
            with self.subTest(relationship=(cleanup_error.__cause__ is not None)):
                scenario = SessionScenario(session_exit_error=cleanup_error)
                server = FakeHighLevelServer(scenario)
                receipt = await run_in_memory_mcp_session(
                    server,
                    expected_tool_names=frozenset({"fictional_snapshot"}),
                    invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
                    timeout_seconds=1.0,
                    lifecycle_adapter=_make_adapter(scenario, server),
                )

                self.assertEqual(receipt.failure_class, "SHUTDOWN_FAILED")
                self.assertFalse(receipt.client_closed)
                self.assertFalse(receipt.server_closed)
                self.assertFalse(receipt.execution_authority)

    async def test_external_task_cancellation_propagates_without_leaking_tasks(self):
        scenario = SessionScenario(call_delay=30.0)
        server = FakeHighLevelServer(scenario)
        task = asyncio.create_task(
            run_in_memory_mcp_session(
                server,
                expected_tool_names=frozenset({"fictional_snapshot"}),
                invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
                timeout_seconds=30.0,
                lifecycle_adapter=_make_adapter(scenario, server),
            )
        )

        for _ in range(20):
            if scenario.call_tool_calls:
                break
            await asyncio.sleep(0)
        self.assertEqual(scenario.call_tool_calls, 1)

        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        pending = [
            pending_task
            for pending_task in asyncio.all_tasks()
            if pending_task is not asyncio.current_task() and not pending_task.done()
        ]
        self.assertEqual(pending, [])
        self.assertEqual(scenario.events[-2:], ["session_exit", "lifespan_exit"])

    async def test_repeated_use_does_not_leak_tasks(self):
        for _ in range(2):
            scenario = SessionScenario()
            server = FakeHighLevelServer(scenario)
            adapter = _make_adapter(scenario, server)
            receipt = await run_in_memory_mcp_session(
                server,
                expected_tool_names=frozenset({"fictional_snapshot"}),
                invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
                timeout_seconds=1.0,
                lifecycle_adapter=adapter,
            )
            self.assertEqual(receipt.failure_class, "NONE")
            self.assertEqual(receipt.broker_request_count, 1)
            pending = [
                task
                for task in asyncio.all_tasks()
                if task is not asyncio.current_task() and not task.done()
            ]
            self.assertEqual(pending, [])

    def test_invocation_arguments_are_immutable(self):
        source = {"symbol": "SPY"}
        invocation = MCPInvocation("fictional_snapshot", source)
        source["symbol"] = "QQQ"
        self.assertEqual(invocation.arguments["symbol"], "SPY")
        with self.assertRaises(TypeError):
            invocation.arguments["symbol"] = "QQQ"  # type: ignore[index]

    def test_invocation_requires_an_existing_mapping_before_copy(self):
        non_mappings = (
            [("symbol", "SPY")],
            (("symbol", "SPY"),),
            iter((("symbol", "SPY"),)),
            "symbol=SPY",
            123,
            1.5,
            True,
            None,
        )
        for arguments in non_mappings:
            with self.subTest(arguments_type=type(arguments).__name__):
                with self.assertRaises(TypeError):
                    MCPInvocation("fictional_snapshot", arguments)  # type: ignore[arg-type]

        invocation = MCPInvocation(
            "fictional_snapshot",
            MappingProxyType({"symbol": "SPY"}),
        )
        self.assertEqual(dict(invocation.arguments), {"symbol": "SPY"})

    def test_receipt_is_value_free_and_immutable(self):
        receipt = MCPSessionReceipt(
            schema_version="004B.mcp-session-harness.v2",
            initialized=True,
            visible_tool_names=("fictional_snapshot",),
            exact_surface_match=True,
            invocation_requested=True,
            invoked_tool_name="fictional_snapshot",
            invocation_completed=True,
            invocation_result_type="dict",
            timeout=False,
            failure_class="NONE",
            client_closed=True,
            server_closed=True,
            broker_request_count=1,
            execution_authority=False,
        )
        self.assertEqual(receipt.failure_class, "NONE")
        with self.assertRaises(Exception):
            receipt.failure_class = "TIMEOUT"  # type: ignore[misc]

    async def test_scenario_1_both_exits_succeed_reports_both_closed(self):
        scenario = SessionScenario()
        server = FakeHighLevelServer(scenario)
        adapter = _make_adapter(scenario, server)

        receipt = await run_in_memory_mcp_session(
            server,
            expected_tool_names=frozenset({"fictional_snapshot"}),
            invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
            timeout_seconds=1.0,
            lifecycle_adapter=adapter,
        )

        self.assertEqual(receipt.failure_class, "NONE")
        self.assertTrue(receipt.client_closed)
        self.assertTrue(receipt.server_closed)
        self.assertFalse(receipt.execution_authority)

    async def test_scenario_2_session_exit_fails_lifespan_exits_reports_neither_closed(self):
        scenario = SessionScenario(session_exit_error=RuntimeError("session shutdown failed"))
        server = FakeHighLevelServer(scenario)
        adapter = _make_adapter(scenario, server)

        receipt = await run_in_memory_mcp_session(
            server,
            expected_tool_names=frozenset({"fictional_snapshot"}),
            invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
            timeout_seconds=1.0,
            lifecycle_adapter=adapter,
        )

        self.assertEqual(receipt.failure_class, "SHUTDOWN_FAILED")
        self.assertFalse(receipt.client_closed)
        self.assertFalse(receipt.server_closed)
        self.assertFalse(receipt.execution_authority)

    async def test_scenario_3_session_exits_lifespan_shutdown_fails_reports_client_closed_only(self):
        scenario = SessionScenario(lifespan_exit_error=RuntimeError("lifespan shutdown failed"))
        server = FakeHighLevelServer(scenario)
        adapter = _make_adapter(scenario, server)

        receipt = await run_in_memory_mcp_session(
            server,
            expected_tool_names=frozenset({"fictional_snapshot"}),
            invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
            timeout_seconds=1.0,
            lifecycle_adapter=adapter,
        )

        self.assertEqual(receipt.failure_class, "SHUTDOWN_FAILED")
        self.assertTrue(receipt.client_closed)
        self.assertFalse(receipt.server_closed)
        self.assertFalse(receipt.execution_authority)

    async def test_scenario_4_both_exit_failures_report_neither_closed(self):
        scenario = SessionScenario(
            session_exit_error=RuntimeError("session shutdown failed"),
            lifespan_exit_error=RuntimeError("lifespan shutdown failed"),
        )
        server = FakeHighLevelServer(scenario)
        adapter = _make_adapter(scenario, server)

        receipt = await run_in_memory_mcp_session(
            server,
            expected_tool_names=frozenset({"fictional_snapshot"}),
            invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
            timeout_seconds=1.0,
            lifecycle_adapter=adapter,
        )

        self.assertEqual(receipt.failure_class, "SHUTDOWN_FAILED")
        self.assertFalse(receipt.client_closed)
        self.assertFalse(receipt.server_closed)
        self.assertFalse(receipt.execution_authority)


if __name__ == "__main__":
    import unittest

    unittest.main()
