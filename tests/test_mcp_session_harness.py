from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from types import ModuleType, SimpleNamespace
from typing import Optional
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from selfbull import mcp_session_harness as harness
from selfbull.mcp_session_harness import MCPInvocation, MCPSessionReceipt, run_in_memory_mcp_session


@dataclass
class SessionScenario:
    visible_tool_names: list[str] = field(default_factory=lambda: ["fictional_snapshot"])
    hidden_tool_names: list[str] = field(default_factory=lambda: ["fictional_mutation"])
    initialize_error: Optional[Exception] = None
    discovery_error: Optional[Exception] = None
    invocation_error: Optional[Exception] = None
    call_delay: float = 0.0
    lifespan_error: Optional[Exception] = None
    extra_tool_schema: dict[str, dict[str, object]] = field(default_factory=dict)


class FakeLowLevelServer:
    def __init__(self, scenario: SessionScenario) -> None:
        self.scenario = scenario
        self.run_calls = 0
        self.init_options_calls = 0
        self.started = False
        self.stopped = False

    def create_initialization_options(self) -> object:
        self.init_options_calls += 1
        return object()

    async def run(self, read_stream, write_stream, initialization_options, raise_exceptions=False, stateless=False) -> None:
        self.run_calls += 1
        self.started = True
        try:
            await asyncio.Event().wait()
        finally:
            self.stopped = True


class FakeClientSession:
    def __init__(self, scenario: SessionScenario, *args, **kwargs) -> None:
        self.scenario = scenario
        self.args = args
        self.kwargs = kwargs
        self.initialize_calls = 0
        self.list_tools_calls = 0
        self.call_tool_calls = 0

    async def initialize(self):
        self.initialize_calls += 1
        if self.scenario.initialize_error is not None:
            raise self.scenario.initialize_error
        return SimpleNamespace(protocolVersion="2024-11-05")

    async def list_tools(self, cursor=None, *, params=None):
        self.list_tools_calls += 1
        if self.scenario.discovery_error is not None:
            raise self.scenario.discovery_error
        tool_names = list(self.scenario.visible_tool_names)
        tools = []
        for name in tool_names:
            tools.append(
                SimpleNamespace(
                    name=name,
                    inputSchema=self.scenario.extra_tool_schema.get(
                        name,
                        {"properties": {"symbol": {"type": "string"}}, "required": ["symbol"]},
                    ),
                )
            )
        return SimpleNamespace(tools=tools)

    async def call_tool(self, name, arguments=None, read_timeout_seconds=None, progress_callback=None, *, meta=None):
        self.call_tool_calls += 1
        if self.scenario.invocation_error is not None:
            raise self.scenario.invocation_error
        if self.scenario.call_delay:
            await asyncio.sleep(self.scenario.call_delay)
        payload = {
            "tool": name,
            "arguments": dict(arguments or {}),
            "symbol": (arguments or {}).get("symbol") or (arguments or {}).get("symbols"),
            "result": "fictional_snapshot",
        }
        return payload


class FakeMemoryTransport:
    def __init__(self, scenario: SessionScenario) -> None:
        self.scenario = scenario
        self.entered = 0
        self.exited = 0

    @asynccontextmanager
    async def create_client_server_memory_streams(self):
        self.entered += 1
        client_streams = (SimpleNamespace(name="client_read"), SimpleNamespace(name="client_write"))
        server_streams = (SimpleNamespace(name="server_read"), SimpleNamespace(name="server_write"))
        try:
            yield client_streams, server_streams
        finally:
            self.exited += 1


class FakeServer:
    def __init__(self, scenario: SessionScenario) -> None:
        self.scenario = scenario
        self._mcp_server = FakeLowLevelServer(scenario)
        self.lifespan_entered = 0
        self.lifespan_exited = 0

    @asynccontextmanager
    async def _lifespan_manager(self):
        self.lifespan_entered += 1
        try:
            if self.scenario.lifespan_error is not None:
                raise self.scenario.lifespan_error
            yield
        finally:
            self.lifespan_exited += 1


def _fake_import_module_factory(scenario: SessionScenario, transport: FakeMemoryTransport):
    fake_memory_module = ModuleType("mcp.shared.memory")
    fake_memory_module.create_client_server_memory_streams = transport.create_client_server_memory_streams

    fake_session_module = ModuleType("mcp.client.session")
    fake_session_module.ClientSession = lambda *args, **kwargs: FakeClientSession(scenario, *args, **kwargs)

    def fake_import_module(name: str, package: Optional[str] = None):
        if name == "mcp.shared.memory":
            return fake_memory_module
        if name == "mcp.client.session":
            return fake_session_module
        return __import__(name, fromlist=["*"])

    return fake_import_module


class TestMCPSessionHarness(IsolatedAsyncioTestCase):
    async def test_fictional_harness_runs_successfully_offline(self):
        scenario = SessionScenario()
        transport = FakeMemoryTransport(scenario)
        server = FakeServer(scenario)

        with patch.object(harness.importlib, "import_module", side_effect=_fake_import_module_factory(scenario, transport)):
            receipt = await run_in_memory_mcp_session(
                server,
                expected_tool_names=frozenset({"fictional_snapshot"}),
                invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
                timeout_seconds=1.0,
            )

        self.assertIsInstance(receipt, MCPSessionReceipt)
        self.assertEqual(receipt.schema_version, "004B.mcp-session-harness.v1")
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
        self.assertEqual(transport.entered, 1)
        self.assertEqual(transport.exited, 1)
        self.assertEqual(server.lifespan_entered, 1)
        self.assertEqual(server.lifespan_exited, 1)
        self.assertEqual(server._mcp_server.run_calls, 1)
        self.assertEqual(server._mcp_server.init_options_calls, 1)

        pending = [task for task in asyncio.all_tasks() if task is not asyncio.current_task() and not task.done()]
        self.assertEqual(pending, [])

    async def test_forbidden_invocation_is_refused_before_handler_lookup(self):
        scenario = SessionScenario()
        transport = FakeMemoryTransport(scenario)
        server = FakeServer(scenario)

        with patch.object(harness.importlib, "import_module", side_effect=_fake_import_module_factory(scenario, transport)):
            receipt = await run_in_memory_mcp_session(
                server,
                expected_tool_names=frozenset({"fictional_snapshot"}),
                invocation=MCPInvocation("fictional_mutation", {"name": "Tech Stocks"}),
                timeout_seconds=1.0,
            )

        self.assertEqual(receipt.failure_class, "TOOL_NOT_ALLOWED")
        self.assertTrue(receipt.invocation_requested)
        self.assertEqual(receipt.invoked_tool_name, "fictional_mutation")
        self.assertFalse(receipt.invocation_completed)
        self.assertEqual(receipt.broker_request_count, 0)
        self.assertEqual(server._mcp_server.run_calls, 1)
        self.assertEqual(transport.entered, 1)
        self.assertEqual(transport.exited, 1)

    async def test_surface_mismatch_blocks_invocation(self):
        scenario = SessionScenario(visible_tool_names=["fictional_snapshot", "fictional_mutation"])
        transport = FakeMemoryTransport(scenario)
        server = FakeServer(scenario)

        with patch.object(harness.importlib, "import_module", side_effect=_fake_import_module_factory(scenario, transport)):
            receipt = await run_in_memory_mcp_session(
                server,
                expected_tool_names=frozenset({"fictional_snapshot"}),
                invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
                timeout_seconds=1.0,
            )

        self.assertEqual(receipt.failure_class, "SURFACE_MISMATCH")
        self.assertFalse(receipt.invocation_completed)
        self.assertEqual(receipt.broker_request_count, 0)
        self.assertEqual(receipt.visible_tool_names, ("fictional_mutation", "fictional_snapshot"))
        self.assertTrue(receipt.client_closed)
        self.assertTrue(receipt.server_closed)

    async def test_timeout_becomes_controlled(self):
        scenario = SessionScenario(call_delay=0.1)
        transport = FakeMemoryTransport(scenario)
        server = FakeServer(scenario)

        with patch.object(harness.importlib, "import_module", side_effect=_fake_import_module_factory(scenario, transport)):
            receipt = await run_in_memory_mcp_session(
                server,
                expected_tool_names=frozenset({"fictional_snapshot"}),
                invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
                timeout_seconds=0.001,
            )

        self.assertEqual(receipt.failure_class, "TIMEOUT")
        self.assertTrue(receipt.timeout)
        self.assertFalse(receipt.invocation_completed)
        self.assertEqual(receipt.broker_request_count, 1)
        self.assertTrue(receipt.client_closed)
        self.assertTrue(receipt.server_closed)

    async def test_tool_exception_becomes_controlled(self):
        scenario = SessionScenario(invocation_error=ValueError("boom"))
        transport = FakeMemoryTransport(scenario)
        server = FakeServer(scenario)

        with patch.object(harness.importlib, "import_module", side_effect=_fake_import_module_factory(scenario, transport)):
            receipt = await run_in_memory_mcp_session(
                server,
                expected_tool_names=frozenset({"fictional_snapshot"}),
                invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
                timeout_seconds=1.0,
            )

        self.assertEqual(receipt.failure_class, "INVOCATION_FAILED")
        self.assertFalse(receipt.invocation_completed)
        self.assertEqual(receipt.broker_request_count, 1)
        self.assertTrue(receipt.client_closed)
        self.assertTrue(receipt.server_closed)

    async def test_initialization_failure_becomes_controlled(self):
        scenario = SessionScenario(initialize_error=RuntimeError("init failed"))
        transport = FakeMemoryTransport(scenario)
        server = FakeServer(scenario)

        with patch.object(harness.importlib, "import_module", side_effect=_fake_import_module_factory(scenario, transport)):
            receipt = await run_in_memory_mcp_session(
                server,
                expected_tool_names=frozenset({"fictional_snapshot"}),
                invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
                timeout_seconds=1.0,
            )

        self.assertEqual(receipt.failure_class, "CLIENT_INITIALIZATION_FAILED")
        self.assertFalse(receipt.initialized)
        self.assertTrue(receipt.client_closed)
        self.assertTrue(receipt.server_closed)
        self.assertEqual(receipt.broker_request_count, 0)

    async def test_lifespan_failure_becomes_controlled(self):
        scenario = SessionScenario(lifespan_error=RuntimeError("lifespan failed"))
        transport = FakeMemoryTransport(scenario)
        server = FakeServer(scenario)

        with patch.object(harness.importlib, "import_module", side_effect=_fake_import_module_factory(scenario, transport)):
            receipt = await run_in_memory_mcp_session(
                server,
                expected_tool_names=frozenset({"fictional_snapshot"}),
                invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
                timeout_seconds=1.0,
            )

        self.assertEqual(receipt.failure_class, "LIFESPAN_START_FAILED")
        self.assertFalse(receipt.initialized)
        self.assertTrue(receipt.client_closed)
        self.assertTrue(receipt.server_closed)
        self.assertEqual(server.lifespan_entered, 1)
        self.assertEqual(server.lifespan_exited, 1)

    async def test_repeated_use_does_not_leak_tasks(self):
        for _ in range(2):
            scenario = SessionScenario()
            transport = FakeMemoryTransport(scenario)
            server = FakeServer(scenario)
            with patch.object(harness.importlib, "import_module", side_effect=_fake_import_module_factory(scenario, transport)):
                receipt = await run_in_memory_mcp_session(
                    server,
                    expected_tool_names=frozenset({"fictional_snapshot"}),
                    invocation=MCPInvocation("fictional_snapshot", {"symbol": "SPY"}),
                    timeout_seconds=1.0,
                )
            self.assertEqual(receipt.failure_class, "NONE")
            self.assertEqual(receipt.broker_request_count, 1)
            pending = [task for task in asyncio.all_tasks() if task is not asyncio.current_task() and not task.done()]
            self.assertEqual(pending, [])

    def test_invocation_arguments_are_immutable(self):
        invocation = MCPInvocation("fictional_snapshot", {"symbol": "SPY"})
        with self.assertRaises(TypeError):
            invocation.arguments["symbol"] = "QQQ"  # type: ignore[index]

    def test_receipt_is_value_free_and_immutable(self):
        receipt = MCPSessionReceipt(
            schema_version="004B.mcp-session-harness.v1",
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


if __name__ == "__main__":
    import unittest

    unittest.main()
