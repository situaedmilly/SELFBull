from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
import os
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from selfbull.mcp_one_tool_composition import (
    CompositionError,
    CompositionReceipt,
    DISCOVERY_ALLOWLIST,
    INVOCATION_ALLOWLIST,
    SNAPSHOT_TOOL_NAME,
    SnapshotOnlyServer,
    build_snapshot_only_server,
    validate_snapshot_only_surface,
)


@dataclass
class FakeTool:
    name: str


class FakeLowLevelServer:
    def __init__(self) -> None:
        self.run_calls = 0
        self.initialization_option_calls = 0

    async def run(self, *_args, **_kwargs):
        self.run_calls += 1

    def create_initialization_options(self):
        self.initialization_option_calls += 1
        return {"capability": "fictional"}

    async def call_tool(self, *_args, **_kwargs):
        raise AssertionError("raw low-level invocation must not be exposed")


class FakeServer:
    def __init__(self, tool_names: list[str]):
        self.tool_names = list(tool_names)
        self.removed: list[str] = []
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.added: list[str] = []
        self.network_called = False
        self.credentials_read = False
        self.server_started = False
        self._mcp_server = FakeLowLevelServer()

    @asynccontextmanager
    async def _lifespan_manager(self):
        yield

    async def list_tools(self):
        return [FakeTool(name) for name in self.tool_names]

    async def call_tool(self, name: str, arguments: dict[str, object]):
        self.calls.append((name, dict(arguments)))
        if name not in self.tool_names:
            raise AssertionError(f"unexpected call: {name}")
        return {"name": name, "arguments": dict(arguments)}

    def remove_tool(self, name: str) -> None:
        self.removed.append(name)
        if name in self.tool_names:
            self.tool_names.remove(name)

    def add_tool(self, name: str) -> None:
        self.added.append(name)
        self.tool_names.append(name)


class TestCompositionContract(unittest.TestCase):
    def test_allowlists_are_exact_and_closed(self):
        self.assertEqual(DISCOVERY_ALLOWLIST, frozenset({SNAPSHOT_TOOL_NAME}))
        self.assertEqual(INVOCATION_ALLOWLIST, frozenset({SNAPSHOT_TOOL_NAME}))

    def test_build_prunes_to_exact_one_tool(self):
        server = FakeServer(
            [
                "get_stock_snapshot",
                "get_watchlists",
                "create_watchlist",
                "place_stock_order",
                "get_account_balance",
                "get_stock_bars_single",
            ]
        )

        composed = build_snapshot_only_server(
            config=SimpleNamespace(toolsets=frozenset({"account", "market-data", "trading"})),
            build_server_fn=lambda _config: server,
        )

        self.assertIsInstance(composed, SnapshotOnlyServer)
        self.assertEqual(composed.receipt.visible_tool_names, ("get_stock_snapshot",))
        self.assertTrue(composed.receipt.exact_surface_match)
        self.assertEqual(server.tool_names, ["get_stock_snapshot"])
        self.assertCountEqual(
            server.removed,
            [
                "get_watchlists",
                "create_watchlist",
                "place_stock_order",
                "get_account_balance",
                "get_stock_bars_single",
            ],
        )
        self.assertFalse(server.network_called)
        self.assertFalse(server.credentials_read)
        self.assertFalse(server.server_started)
        self.assertFalse(composed.receipt.mcp_authenticated)
        self.assertFalse(composed.receipt.mcp_server_started)
        self.assertEqual(composed.receipt.broker_request_count, 0)
        self.assertFalse(composed.receipt.sdk_called)
        self.assertFalse(composed.receipt.execution_authority)
        self.assertIsNot(composed._server, server)
        self.assertIsNot(composed._server._mcp_server, server._mcp_server)
        self.assertFalse(hasattr(composed, "call_tool"))
        self.assertFalse(hasattr(composed, "list_tools"))
        self.assertFalse(hasattr(composed._server, "call_tool"))
        self.assertFalse(hasattr(composed._server, "list_tools"))
        self.assertFalse(hasattr(composed._server, "remove_tool"))
        self.assertFalse(hasattr(composed._server, "add_tool"))
        self.assertFalse(hasattr(composed._server._mcp_server, "call_tool"))
        self.assertFalse(hasattr(composed._server._mcp_server, "_run"))
        self.assertFalse(hasattr(composed._server._mcp_server, "__dict__"))
        self.assertIs(composed._server._lifespan_manager.__self__, composed._server)
        self.assertIs(composed._server._mcp_server.run.__self__, composed._server._mcp_server)
        with self.assertRaises(AttributeError):
            composed._server._mcp_server = server._mcp_server  # type: ignore[misc]
        self.assertEqual(
            composed._server._mcp_server.create_initialization_options(),
            {"capability": "fictional"},
        )

    def test_generic_facade_invocation_and_raw_server_escape_are_absent(self):
        server = FakeServer(["get_stock_snapshot", "create_watchlist"])
        composed = build_snapshot_only_server(config=object(), build_server_fn=lambda _config: server)

        self.assertFalse(hasattr(composed, "call_tool"))
        self.assertFalse(hasattr(composed._server, "call_tool"))
        self.assertFalse(hasattr(composed._server._mcp_server, "call_tool"))
        self.assertEqual(server.calls, [])

    def test_unknown_and_malformed_names_fail_closed(self):
        receipt = validate_snapshot_only_surface(FakeServer(["get_stock_snapshot", "get_watchlists"]))
        self.assertFalse(receipt.exact_surface_match)
        self.assertEqual(receipt.forbidden_visible_tool_names, ("get_watchlists",))

        with self.assertRaises(CompositionError):
            validate_snapshot_only_surface(FakeServer(["get_stock_snapshot", ""]))

        with self.assertRaises(CompositionError):
            validate_snapshot_only_surface(FakeServer(["get_stock_snapshot", "get_stock_snapshot"]))

        for malformed in (
            " get_stock_snapshot",
            "get_stock_snapshot ",
            "\tget_stock_snapshot",
            "get_stock_snapshot\n",
            "get_stock_snapshot\u00a0",
        ):
            with self.subTest(malformed=repr(malformed)):
                with self.assertRaises(CompositionError):
                    validate_snapshot_only_surface(FakeServer([malformed]))

    def test_future_upstream_tools_remain_disabled_after_composition(self):
        server = FakeServer(["get_stock_snapshot", "get_stock_latest_news", "get_watchlists"])
        composed = build_snapshot_only_server(config=object(), build_server_fn=lambda _config: server)

        self.assertEqual(composed.receipt.visible_tool_names, ("get_stock_snapshot",))
        self.assertEqual(server.tool_names, ["get_stock_snapshot"])
        self.assertEqual(server.removed, ["get_stock_latest_news", "get_watchlists"])

    def test_mutation_after_validation_is_detected(self):
        server = FakeServer(["get_stock_snapshot"])
        composed = build_snapshot_only_server(config=object(), build_server_fn=lambda _config: server)

        server.add_tool("create_watchlist")

        drift_receipt = validate_snapshot_only_surface(server)
        self.assertFalse(drift_receipt.exact_surface_match)
        self.assertEqual(drift_receipt.forbidden_visible_tool_names, ("create_watchlist",))
        self.assertFalse(hasattr(composed, "call_tool"))

    def test_refuses_when_surface_cannot_be_pruned_to_one_tool(self):
        server = FakeServer(["get_stock_snapshot", "create_watchlist"])
        server.remove_tool = None  # type: ignore[assignment]

        with self.assertRaises(CompositionError):
            build_snapshot_only_server(config=object(), build_server_fn=lambda _config: server)

    def test_refuses_server_without_bounded_lifecycle_capability(self):
        server = FakeServer(["get_stock_snapshot"])
        server._mcp_server = None

        with self.assertRaises(CompositionError):
            build_snapshot_only_server(config=object(), build_server_fn=lambda _config: server)

    def test_receipt_has_safe_value_free_fields(self):
        receipt = validate_snapshot_only_surface(FakeServer(["get_stock_snapshot"]))
        self.assertIsInstance(receipt, CompositionReceipt)
        self.assertEqual(receipt.schema_version, "004B.mcp-one-tool-composition.v1")
        self.assertEqual(receipt.visible_tool_names, ("get_stock_snapshot",))
        self.assertEqual(receipt.forbidden_visible_tool_names, ())
        self.assertEqual(receipt.discovery_allowlist, DISCOVERY_ALLOWLIST)
        self.assertEqual(receipt.invocation_allowlist, INVOCATION_ALLOWLIST)
        self.assertEqual(receipt.verdict, "SEALED")


if __name__ == "__main__":
    unittest.main()
