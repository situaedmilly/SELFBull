"""Hostile offline tests for the SELFBULL-004B MCP inventory inspector."""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import selfbull.mcp_inventory as inventory  # noqa: E402
from selfbull.mcp_inventory import (  # noqa: E402
    CLEANUP_CLEAN,
    CLEANUP_FAILED,
    FAILURE_CLEANUP,
    FAILURE_NONE,
    FAILURE_OUTPUT_PARSE,
    FAILURE_PROCESS_SPAWN,
    FAILURE_PROCESS_TIMEOUT,
    FAILURE_RECEIPT_VERIFY,
    FAILURE_RECEIPT_WRITE,
    FAILURE_UNEXPECTED,
    INVENTORY_COMMAND,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_TIMEOUT,
    InventoryBoundaryError,
    InventoryParseError,
    InventorySafetyError,
    ProcessOutcome,
    _ReceiptWriteError,
    _run_process,
    inspect_inventory,
    parse_inventory_output,
)


REAL_CLI_SHAPED_INVENTORY = """
Webull OpenAPI MCP Server Tools
============================================================

Total: 3 tools

  get_stock_bars_single
    Get OHLCV bars for a single stock.

  get_stock_quotes
    Get real-time stock bid/ask quotes with depth.

  get_stock_snapshot
    Get real-time stock/ETF snapshot. Supports multiple symbols.
"""

FORBIDDEN_INVENTORY = """
  get_stock_snapshot
    Get real-time stock/ETF snapshot.
  get_account_balance
    Get account balances and assets.
  place_stock_order
    Place a stock order.
"""

WATCHLIST_INVENTORY = """
  get_stock_snapshot
    Get real-time stock/ETF snapshot.
  get_watchlists
    Get all watchlists.
  create_watchlist
    Create a watchlist.
  update_watchlist_instruments
    Update instrument sort order.
"""


def environment():
    return {
        "WEBULL_APP_KEY": "fictional-key",
        "WEBULL_APP_SECRET": "fictional-secret",
        "WEBULL_REGION_ID": "us",
        "WEBULL_ENVIRONMENT": "prod",
        "WEBULL_TOOLSETS": "market-data",
    }


def successful_runner(command, *, stdout, stderr, **_kwargs):
    stdout.write(REAL_CLI_SHAPED_INVENTORY.encode())
    stdout.flush()
    return ProcessOutcome(returncode=0, timed_out=False)


def removing_cleanup_then_fail(path):
    shutil.rmtree(path)
    raise OSError("fictional cleanup failure")


def current_umask():
    observed = os.umask(0o077)
    os.umask(observed)
    return observed


def pid_exists(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class TestInventoryParser(unittest.TestCase):
    def test_real_cli_shape_parses_tool_names_only(self):
        receipt = parse_inventory_output(REAL_CLI_SHAPED_INVENTORY)
        self.assertEqual(
            receipt["tool_names"],
            ["get_stock_bars_single", "get_stock_quotes", "get_stock_snapshot"],
        )
        self.assertEqual(receipt["schema_inventory_state"], "NOT_AVAILABLE_FROM_TOOLS_COMMAND")
        self.assertNotIn("input_schema_field_names", receipt)
        self.assertTrue(receipt["market_data_tools_exposed"])
        self.assertEqual(receipt["selected_snapshot_tool"], "get_stock_snapshot")

    def test_description_text_is_not_retained(self):
        receipt = parse_inventory_output(REAL_CLI_SHAPED_INVENTORY)
        self.assertNotIn("Get real-time", json.dumps(receipt))

    def test_strips_ansi_without_retaining_terminal_codes(self):
        receipt = parse_inventory_output("\x1b[32mget_stock_snapshot\x1b[0m\n  Description\n")
        self.assertEqual(receipt["tool_names"], ["get_stock_snapshot"])
        self.assertNotIn("\x1b", json.dumps(receipt))

    def test_account_and_trading_tools_are_forbidden(self):
        with self.assertRaises(InventoryBoundaryError) as caught:
            parse_inventory_output(FORBIDDEN_INVENTORY)
        self.assertEqual(caught.exception.forbidden_classes, ("account", "trading"))

    def test_watchlist_reads_and_mutations_are_forbidden(self):
        with self.assertRaises(InventoryBoundaryError) as caught:
            parse_inventory_output(WATCHLIST_INVENTORY)
        self.assertEqual(caught.exception.forbidden_classes, ("account",))
        self.assertEqual(
            caught.exception.forbidden_tool_names,
            ("create_watchlist", "get_watchlists", "update_watchlist_instruments"),
        )

    def test_malformed_inventory_fails_cleanly(self):
        for raw in ("", "No callable surface was rendered.", "tool with spaces"):
            with self.subTest(raw=raw):
                with self.assertRaises(InventoryParseError):
                    parse_inventory_output(raw)

    def test_fake_credential_value_is_refused_without_reproduction(self):
        fake_value = "fictional-secret-value-never-return"
        with self.assertRaises(InventorySafetyError) as caught:
            parse_inventory_output(f"get_stock_snapshot\nAPP_SECRET={fake_value}\n")
        self.assertNotIn(fake_value, str(caught.exception))


class TestImmutableCommand(unittest.TestCase):
    def test_canonical_command_is_immutable(self):
        self.assertIsInstance(INVENTORY_COMMAND, tuple)
        with self.assertRaises(TypeError):
            INVENTORY_COMMAND[0] = "mutated"  # type: ignore[index]

    def test_execution_receives_the_exact_command(self):
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return successful_runner(command, **kwargs)

        with tempfile.TemporaryDirectory() as parent:
            result = inspect_inventory(
                env=environment(), process_runner=runner, temp_parent=Path(parent)
            )
        self.assertEqual(calls[0][0], INVENTORY_COMMAND)
        self.assertEqual(result["status"], STATUS_COMPLETED)


class TestProcessGroupTimeout(unittest.TestCase):
    def test_parent_and_child_are_killed_and_reaped(self):
        child_code = "import time; time.sleep(60)"
        parent_code = (
            "import subprocess,sys,time; "
            "child=subprocess.Popen([sys.executable,'-c',sys.argv[1]]); "
            "print(child.pid, flush=True); time.sleep(60)"
        )
        with tempfile.TemporaryDirectory() as parent:
            stdout_path = Path(parent) / "stdout"
            stderr_path = Path(parent) / "stderr"
            with stdout_path.open("wb") as out_file, stderr_path.open("wb") as err_file:
                outcome = _run_process(
                    (sys.executable, "-c", parent_code, child_code),
                    env=os.environ,
                    stdout=out_file,
                    stderr=err_file,
                    timeout=0.2,
                    grace_period=0.2,
                )
            child_pid = int(stdout_path.read_text().strip())
            deadline = time.monotonic() + 3
            while pid_exists(child_pid) and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(outcome.timed_out)
            self.assertFalse(pid_exists(child_pid))

    def test_timeout_is_a_controlled_public_result(self):
        def runner(*_args, **_kwargs):
            return ProcessOutcome(returncode=-15, timed_out=True)

        with tempfile.TemporaryDirectory() as parent:
            result = inspect_inventory(
                env=environment(), process_runner=runner, temp_parent=Path(parent)
            )
            self.assertEqual(list(Path(parent).iterdir()), [])
        self.assertEqual(result["status"], STATUS_TIMEOUT)
        self.assertEqual(result["failure_class"], FAILURE_PROCESS_TIMEOUT)
        self.assertEqual(result["cleanup_status"], CLEANUP_CLEAN)


class TestChamberLifecycle(unittest.TestCase):
    def test_chamber_creation_failure_is_controlled_and_umask_restored(self):
        original = os.umask(0o027)
        try:
            def fail_creation(**_kwargs):
                raise PermissionError("fictional path")

            result = inspect_inventory(env=environment(), temp_dir_factory=fail_creation)
            self.assertEqual(result["failure_class"], FAILURE_UNEXPECTED)
            self.assertEqual(current_umask(), 0o027)
        finally:
            os.umask(original)

    def test_chmod_failure_cleans_chamber_and_restores_umask(self):
        original = os.umask(0o027)
        try:
            with tempfile.TemporaryDirectory() as parent:
                def fail_chmod(*_args):
                    raise PermissionError("fictional chmod")

                result = inspect_inventory(
                    env=environment(), temp_parent=Path(parent), chmod_func=fail_chmod
                )
                self.assertEqual(list(Path(parent).iterdir()), [])
            self.assertEqual(result["failure_class"], FAILURE_UNEXPECTED)
            self.assertEqual(current_umask(), 0o027)
        finally:
            os.umask(original)

    def test_cleanup_failure_is_explicit(self):
        with tempfile.TemporaryDirectory() as parent:
            result = inspect_inventory(
                env=environment(),
                process_runner=successful_runner,
                temp_parent=Path(parent),
                cleanup_func=removing_cleanup_then_fail,
            )
            self.assertEqual(list(Path(parent).iterdir()), [])
        self.assertEqual(result["status"], STATUS_FAILED)
        self.assertEqual(result["failure_class"], FAILURE_CLEANUP)
        self.assertEqual(result["cleanup_status"], CLEANUP_FAILED)
        self.assertEqual(result["cleanup_failure_class"], FAILURE_CLEANUP)

    def test_original_failure_survives_cleanup_failure(self):
        def spawn_failure(*_args, **_kwargs):
            raise OSError("fictional spawn path")

        with tempfile.TemporaryDirectory() as parent:
            result = inspect_inventory(
                env=environment(),
                process_runner=spawn_failure,
                temp_parent=Path(parent),
                cleanup_func=removing_cleanup_then_fail,
            )
        self.assertEqual(result["failure_class"], FAILURE_PROCESS_SPAWN)
        self.assertEqual(result["cleanup_status"], CLEANUP_FAILED)

    def test_umask_restored_after_success(self):
        original = os.umask(0o027)
        try:
            with tempfile.TemporaryDirectory() as parent:
                result = inspect_inventory(
                    env=environment(), process_runner=successful_runner, temp_parent=Path(parent)
                )
            self.assertEqual(result["status"], STATUS_COMPLETED)
            self.assertEqual(current_umask(), 0o027)
        finally:
            os.umask(original)


class TestControlledFailureSurface(unittest.TestCase):
    def run_with(self, runner=successful_runner, **kwargs):
        with tempfile.TemporaryDirectory() as parent:
            result = inspect_inventory(
                env=environment(),
                process_runner=runner,
                temp_parent=Path(parent),
                **kwargs,
            )
            self.assertEqual(list(Path(parent).iterdir()), [])
            return result

    def test_spawn_errors_are_controlled(self):
        for error in (OSError("fictional path"), PermissionError("fictional permission")):
            with self.subTest(error=type(error).__name__):
                def runner(*_args, **_kwargs):
                    raise error

                result = self.run_with(runner)
                self.assertEqual(result["failure_class"], FAILURE_PROCESS_SPAWN)

    def test_injected_timeout_exception_is_controlled(self):
        def runner(*_args, **_kwargs):
            raise subprocess.TimeoutExpired(("fictional",), 1)

        result = self.run_with(runner)
        self.assertEqual(result["status"], STATUS_TIMEOUT)
        self.assertEqual(result["failure_class"], FAILURE_PROCESS_TIMEOUT)

    def test_unexpected_exception_is_controlled(self):
        def runner(*_args, **_kwargs):
            raise RuntimeError("fictional raw detail")

        result = self.run_with(runner)
        blob = json.dumps(result)
        self.assertEqual(result["failure_class"], FAILURE_UNEXPECTED)
        self.assertNotIn("fictional raw detail", blob)

    def test_malformed_output_is_controlled(self):
        def runner(command, *, stdout, **_kwargs):
            stdout.write(b"not a tool inventory")
            stdout.flush()
            return ProcessOutcome(returncode=0, timed_out=False)

        result = self.run_with(runner)
        self.assertEqual(result["failure_class"], FAILURE_OUTPUT_PARSE)

    def test_nonzero_command_is_controlled(self):
        def runner(command, *, stderr, **_kwargs):
            stderr.write(b"fictional static failure")
            stderr.flush()
            return ProcessOutcome(returncode=2, timed_out=False)

        result = self.run_with(runner)
        self.assertEqual(result["failure_class"], FAILURE_OUTPUT_PARSE)

    def test_receipt_write_and_fsync_failures_are_controlled(self):
        def write_failure(*_args, **_kwargs):
            raise _ReceiptWriteError("fictional")

        result = self.run_with(receipt_writer=write_failure)
        self.assertEqual(result["failure_class"], FAILURE_RECEIPT_WRITE)

        def fsync_failure(_fd):
            raise OSError("fictional fsync")

        result = self.run_with(fsync_func=fsync_failure)
        self.assertEqual(result["failure_class"], FAILURE_RECEIPT_WRITE)

    def test_replace_and_reopen_parse_failures_are_controlled(self):
        def replace_failure(_source, _target):
            raise OSError("fictional replace")

        result = self.run_with(replace_func=replace_failure)
        self.assertEqual(result["failure_class"], FAILURE_RECEIPT_VERIFY)

        reads = {"count": 0}

        def invalid_verified_read(path):
            reads["count"] += 1
            if reads["count"] == 1:
                return path.read_text(encoding="utf-8")
            return "not-json"

        result = self.run_with(read_text_func=invalid_verified_read)
        self.assertEqual(result["failure_class"], FAILURE_RECEIPT_VERIFY)

    def test_fake_secret_is_never_returned(self):
        fake_value = "fictional-secret-value-never-return"

        def runner(command, *, stdout, **_kwargs):
            stdout.write(f"get_stock_snapshot\nAPP_SECRET={fake_value}\n".encode())
            stdout.flush()
            return ProcessOutcome(returncode=0, timed_out=False)

        result = self.run_with(runner)
        self.assertEqual(result["failure_class"], FAILURE_OUTPUT_PARSE)
        self.assertNotIn(fake_value, json.dumps(result))

    def test_wrong_toolset_never_runs_subprocess(self):
        env = environment()
        env["WEBULL_TOOLSETS"] = "account,market-data"
        called = []

        def runner(*_args, **_kwargs):
            called.append(True)

        result = inspect_inventory(env=env, process_runner=runner)
        self.assertFalse(called)
        self.assertEqual(result["failure_class"], FAILURE_OUTPUT_PARSE)

    def test_main_never_emits_traceback_for_unexpected_error(self):
        output = io.StringIO()
        with patch.object(inventory, "inspect_inventory", side_effect=RuntimeError("raw detail")):
            with redirect_stdout(output):
                exit_code = inventory.main()
        rendered = output.getvalue()
        self.assertEqual(exit_code, 2)
        self.assertNotIn("Traceback", rendered)
        self.assertNotIn("raw detail", rendered)
        self.assertEqual(json.loads(rendered)["failure_class"], FAILURE_UNEXPECTED)


class TestAuthorityAndReceiptInvariants(unittest.TestCase):
    def test_success_receipt_is_atomic_value_free_and_nonexecuting(self):
        with tempfile.TemporaryDirectory() as parent:
            result = inspect_inventory(
                env=environment(), process_runner=successful_runner, temp_parent=Path(parent)
            )
            self.assertEqual(list(Path(parent).iterdir()), [])
        blob = json.dumps(result)
        self.assertEqual(result["status"], STATUS_COMPLETED)
        self.assertEqual(result["failure_class"], FAILURE_NONE)
        self.assertTrue(result["atomic_receipt_verified"])
        self.assertTrue(result["ephemeral_removed"])
        self.assertNotIn("fictional-key", blob)
        self.assertNotIn("fictional-secret", blob)
        self.assertFalse(result["mcp_authenticated"])
        self.assertFalse(result["mcp_server_started"])
        self.assertEqual(result["broker_request_count"], 0)
        self.assertFalse(result["sdk_called"])
        self.assertFalse(result["fixture_admitted"])
        self.assertFalse(result["execution_authority"])

    def test_watchlist_inventory_returns_controlled_boundary_result(self):
        def runner(command, *, stdout, **_kwargs):
            stdout.write(WATCHLIST_INVENTORY.encode())
            stdout.flush()
            return ProcessOutcome(returncode=0, timed_out=False)

        with tempfile.TemporaryDirectory() as parent:
            result = inspect_inventory(
                env=environment(), process_runner=runner, temp_parent=Path(parent)
            )
            self.assertEqual(list(Path(parent).iterdir()), [])
        self.assertEqual(result["verdict"], "TOOLSET_CONFIGURATION_FAILED")
        self.assertEqual(result["forbidden_classes"], ["account"])
        self.assertIn("create_watchlist", result["forbidden_tool_names"])


if __name__ == "__main__":
    unittest.main()
