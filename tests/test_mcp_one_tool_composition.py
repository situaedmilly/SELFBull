from __future__ import annotations

import asyncio
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


class FakeServer:
    def __init__(self, tool_names: list[str]):
        self.tool_names = list(tool_names)
        self.removed: list[str] = []
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.added: list[str] = []
        self.network_called = False
        self.credentials_read = False
        self.server_started = False

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
        self.assertEqual(asyncio.run(composed.list_tools()), ("get_stock_snapshot",))
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

    def test_snapshot_invocation_is_permitted_and_other_tools_refuse(self):
        server = FakeServer(["get_stock_snapshot", "create_watchlist"])
        composed = build_snapshot_only_server(config=object(), build_server_fn=lambda _config: server)

        result = asyncio.run(composed.call_tool("get_stock_snapshot", {"symbol": "SPY"}))
        self.assertEqual(result["name"], "get_stock_snapshot")
        self.assertEqual(server.calls, [("get_stock_snapshot", {"symbol": "SPY"})])

        with self.assertRaises(CompositionError):
            asyncio.run(composed.call_tool("create_watchlist", {"name": "Tech Stocks"}))

        with self.assertRaises(CompositionError):
            asyncio.run(composed.call_tool("get_account_balance", {}))

        with self.assertRaises(CompositionError):
            asyncio.run(composed.call_tool("place_stock_order", {}))

    def test_unknown_and_malformed_names_fail_closed(self):
        receipt = validate_snapshot_only_surface(FakeServer(["get_stock_snapshot", "get_watchlists"]))
        self.assertFalse(receipt.exact_surface_match)
        self.assertEqual(receipt.forbidden_visible_tool_names, ("get_watchlists",))

        with self.assertRaises(CompositionError):
            validate_snapshot_only_surface(FakeServer(["get_stock_snapshot", ""]))

        with self.assertRaises(CompositionError):
            validate_snapshot_only_surface(FakeServer(["get_stock_snapshot", "get_stock_snapshot"]))

    def test_future_upstream_tools_remain_disabled_after_composition(self):
        server = FakeServer(["get_stock_snapshot", "get_stock_latest_news", "get_watchlists"])
        composed = build_snapshot_only_server(config=object(), build_server_fn=lambda _config: server)

        self.assertEqual(asyncio.run(composed.list_tools()), ("get_stock_snapshot",))
        self.assertEqual(server.tool_names, ["get_stock_snapshot"])
        self.assertEqual(server.removed, ["get_stock_latest_news", "get_watchlists"])

    def test_mutation_after_validation_is_detected(self):
        server = FakeServer(["get_stock_snapshot"])
        composed = build_snapshot_only_server(config=object(), build_server_fn=lambda _config: server)

        server.add_tool("create_watchlist")

        with self.assertRaises(CompositionError):
            asyncio.run(composed.list_tools())

        with self.assertRaises(CompositionError):
            asyncio.run(composed.call_tool("get_stock_snapshot", {"symbol": "SPY"}))

    def test_refuses_when_surface_cannot_be_pruned_to_one_tool(self):
        server = FakeServer(["get_stock_snapshot", "create_watchlist"])
        server.remove_tool = None  # type: ignore[assignment]

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
