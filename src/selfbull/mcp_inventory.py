"""Fail-closed SELFBULL-004B inspector for Local MCP tool inventory.

The only permitted subprocess is ``uvx webull-openapi-mcp tools``. This
module never authenticates, starts an MCP server, invokes a discovered tool,
or calls a broker. Raw inventory output exists only in a protected temporary
chamber and never enters the returned receipt.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping, Optional, Sequence, Tuple


INVENTORY_COMMAND = (
    "uvx",
    "webull-openapi-mcp",
    "tools",
)

REQUIRED_ENVIRONMENT = (
    "WEBULL_APP_KEY",
    "WEBULL_APP_SECRET",
    "WEBULL_REGION_ID",
    "WEBULL_ENVIRONMENT",
    "WEBULL_TOOLSETS",
)

STATUS_COMPLETED = "COMPLETED"
STATUS_TIMEOUT = "TIMEOUT"
STATUS_FAILED = "FAILED"

FAILURE_NONE = "NONE"
FAILURE_PROCESS_TIMEOUT = "PROCESS_TIMEOUT"
FAILURE_PROCESS_SPAWN = "PROCESS_SPAWN_ERROR"
FAILURE_OUTPUT_PARSE = "OUTPUT_PARSE_ERROR"
FAILURE_RECEIPT_WRITE = "RECEIPT_WRITE_ERROR"
FAILURE_RECEIPT_VERIFY = "RECEIPT_VERIFY_ERROR"
FAILURE_CLEANUP = "CLEANUP_ERROR"
FAILURE_UNEXPECTED = "UNEXPECTED_ERROR"

CLEANUP_CLEAN = "CLEAN"
CLEANUP_FAILED = "CLEANUP_FAILED"

_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_TOOL_RE = re.compile(
    r"^\s*(?:[-*•🔧]\s*)?"
    r"((?:get|create|update|delete|add|remove|place|preview|replace|cancel|submit)"
    r"_[a-z0-9_]+)\b",
    re.IGNORECASE,
)
_SECRET_VALUE_RE = re.compile(
    r"(?i)(?:app[_ -]?key|app[_ -]?secret|client[_ -]?secret|access[_ -]?token|"
    r"refresh[_ -]?token|authorization|bearer|signature)\s*[:=]\s*\S+"
)

_ACCOUNT_MARKERS = ("account", "balance", "position", "watchlist", "asset")
_TRADING_MARKERS = (
    "order",
    "trade",
    "place_",
    "preview_",
    "replace_",
    "cancel_",
    "submit_",
    "transfer",
    "algo",
)
_MARKET_DATA_MARKERS = ("snapshot", "bars", "quotes", "tick", "footprint", "noii")


class InventoryError(RuntimeError):
    """Base class for internal, value-free inventory failures."""


class InventoryParseError(InventoryError):
    """Raised when tool names cannot be safely admitted."""


class InventorySafetyError(InventoryError):
    """Raised when inventory output appears to contain a credential value."""


class InventoryBoundaryError(InventoryError):
    """Raised when exposed authority exceeds market-data observation."""

    def __init__(
        self,
        message: str,
        *,
        forbidden_classes: Iterable[str] = (),
        forbidden_tool_names: Iterable[str] = (),
    ) -> None:
        super().__init__(message)
        self.forbidden_classes = tuple(sorted(set(forbidden_classes)))
        self.forbidden_tool_names = tuple(sorted(set(forbidden_tool_names)))


class _ReceiptWriteError(InventoryError):
    pass


class _ReceiptVerifyError(InventoryError):
    pass


class _ProcessGroupTerminationError(InventoryError):
    """Raised when a timed-out subprocess group cannot be proven absent."""


@dataclass(frozen=True)
class ProcessOutcome:
    returncode: int
    timed_out: bool


def _decode(payload: bytes) -> str:
    return payload.decode("utf-8", errors="replace")


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _process_group_exists(
    process_group_id: int,
    *,
    killpg: Callable[[int, int], None] = os.killpg,
) -> bool:
    try:
        killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_for_process_group_exit(
    process_group_id: int,
    *,
    timeout: float,
    group_exists: Callable[[int], bool],
) -> bool:
    deadline = time.monotonic() + max(timeout, 0)
    while group_exists(process_group_id):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(0.01, remaining))
    return True


def _terminate_process_group(
    process: subprocess.Popen,
    *,
    grace_period: float,
    killpg: Callable[[int, int], None] = os.killpg,
    group_exists: Optional[Callable[[int], bool]] = None,
) -> int:
    """Terminate, prove absent, and reap the whole process group."""
    process_group_id = process.pid
    if group_exists is None:
        group_exists = lambda pid: _process_group_exists(pid, killpg=killpg)

    try:
        killpg(process_group_id, signal.SIGTERM)
    except ProcessLookupError:
        pass

    parent_returncode: Optional[int] = None
    try:
        parent_returncode = process.wait(timeout=grace_period)
    except subprocess.TimeoutExpired:
        pass

    group_gone = _wait_for_process_group_exit(
        process_group_id,
        timeout=grace_period,
        group_exists=group_exists,
    )
    if not group_gone:
        try:
            killpg(process_group_id, signal.SIGKILL)
        except ProcessLookupError:
            pass

    if parent_returncode is None:
        try:
            parent_returncode = process.wait(timeout=grace_period)
        except subprocess.TimeoutExpired as exc:
            raise _ProcessGroupTerminationError(
                "timed-out process parent could not be reaped"
            ) from exc

    if not _wait_for_process_group_exit(
        process_group_id,
        timeout=grace_period,
        group_exists=group_exists,
    ):
        raise _ProcessGroupTerminationError(
            "timed-out process group could not be proven absent"
        )
    return parent_returncode


def _run_process(
    command: Sequence[str],
    *,
    env: Mapping[str, str],
    stdout: object,
    stderr: object,
    timeout: float = 30,
    grace_period: float = 1,
    popen_factory: Callable[..., subprocess.Popen] = subprocess.Popen,
    killpg: Callable[[int, int], None] = os.killpg,
    group_exists: Optional[Callable[[int], bool]] = None,
) -> ProcessOutcome:
    """Run one command in a new session and kill all descendants on timeout."""
    process = popen_factory(
        list(command),
        env=dict(env),
        stdout=stdout,
        stderr=stderr,
        shell=False,
        start_new_session=True,
    )
    try:
        return ProcessOutcome(returncode=process.wait(timeout=timeout), timed_out=False)
    except subprocess.TimeoutExpired:
        returncode = _terminate_process_group(
            process,
            grace_period=grace_period,
            killpg=killpg,
            group_exists=group_exists,
        )
        return ProcessOutcome(returncode=returncode, timed_out=True)


def _classify_authority(tool_names: Sequence[str]) -> Tuple[list, list]:
    account_tools = [
        name for name in tool_names if any(marker in name for marker in _ACCOUNT_MARKERS)
    ]
    trading_tools = [
        name for name in tool_names if any(marker in name for marker in _TRADING_MARKERS)
    ]
    return account_tools, trading_tools


def parse_inventory_output(raw_output: str) -> dict:
    """Parse only tool names from the real CLI-shaped inventory output."""
    if _SECRET_VALUE_RE.search(raw_output):
        raise InventorySafetyError("credential-like value detected")

    lines = _ANSI_RE.sub("", raw_output).splitlines()
    tool_names = sorted(
        {
            match.group(1).lower()
            for line in lines
            for match in [_TOOL_RE.match(line)]
            if match is not None
        }
    )
    if not tool_names:
        raise InventoryParseError("no callable tool names recognized")

    account_tools, trading_tools = _classify_authority(tool_names)
    forbidden_classes = []
    if account_tools:
        forbidden_classes.append("account")
    if trading_tools:
        forbidden_classes.append("trading")
    if forbidden_classes:
        raise InventoryBoundaryError(
            "forbidden authority exposed",
            forbidden_classes=forbidden_classes,
            forbidden_tool_names=account_tools + trading_tools,
        )

    market_data_tools = [
        name for name in tool_names if any(marker in name for marker in _MARKET_DATA_MARKERS)
    ]
    return {
        "schema_version": "004B.mcp-inventory.v2",
        "tool_names": tool_names,
        "tool_count": len(tool_names),
        "market_data_tools_exposed": bool(market_data_tools),
        "account_tools_exposed": False,
        "trading_tools_exposed": False,
        "selected_snapshot_tool": (
            "get_stock_snapshot" if "get_stock_snapshot" in tool_names else None
        ),
        "schema_inventory_state": "NOT_AVAILABLE_FROM_TOOLS_COMMAND",
        "secret_value_detected": False,
        "raw_output_committed": False,
        "mcp_server_started": False,
        "broker_request_count": 0,
        "execution_authority": False,
    }


def _validate_receipt(receipt: Mapping[str, object]) -> None:
    if receipt.get("schema_version") != "004B.mcp-inventory.v2":
        raise _ReceiptVerifyError("receipt schema invalid")
    if not isinstance(receipt.get("tool_names"), list) or not receipt["tool_names"]:
        raise _ReceiptVerifyError("receipt tool inventory invalid")
    if receipt.get("schema_inventory_state") != "NOT_AVAILABLE_FROM_TOOLS_COMMAND":
        raise _ReceiptVerifyError("schema inventory state invalid")
    for key in (
        "account_tools_exposed",
        "trading_tools_exposed",
        "raw_output_committed",
        "mcp_server_started",
        "execution_authority",
    ):
        if receipt.get(key) is not False:
            raise _ReceiptVerifyError("receipt authority invariant invalid")


def _default_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_and_verify_receipt(
    receipt: Mapping[str, object],
    pending_path: Path,
    verified_path: Path,
    *,
    fsync_func: Callable[[int], None] = os.fsync,
    replace_func: Callable[[object, object], None] = os.replace,
    read_text_func: Callable[[Path], str] = _default_read_text,
) -> dict:
    try:
        with pending_path.open("w", encoding="utf-8") as pending_file:
            json.dump(receipt, pending_file, indent=2, sort_keys=True)
            pending_file.write("\n")
            pending_file.flush()
            fsync_func(pending_file.fileno())
        os.chmod(pending_path, 0o600)
    except Exception as exc:
        raise _ReceiptWriteError("receipt write failed") from exc

    try:
        pending_receipt = json.loads(read_text_func(pending_path))
        _validate_receipt(pending_receipt)
        replace_func(pending_path, verified_path)
        os.chmod(verified_path, 0o600)
        verified_receipt = json.loads(read_text_func(verified_path))
        _validate_receipt(verified_receipt)
        return dict(verified_receipt)
    except Exception as exc:
        if isinstance(exc, _ReceiptVerifyError):
            raise
        raise _ReceiptVerifyError("receipt verification failed") from exc


def _base_result(presence: Mapping[str, bool]) -> dict:
    return {
        "schema_version": "004B.mcp-inventory-result.v2",
        "status": STATUS_FAILED,
        "failure_class": FAILURE_UNEXPECTED,
        "cleanup_status": CLEANUP_CLEAN,
        "cleanup_failure_class": FAILURE_NONE,
        "ephemeral_removed": True,
        "atomic_receipt_verified": False,
        "credential_presence": {
            "WEBULL_APP_KEY": bool(presence.get("WEBULL_APP_KEY")),
            "WEBULL_APP_SECRET": bool(presence.get("WEBULL_APP_SECRET")),
        },
        "toolset": "market-data",
        "tool_names": [],
        "forbidden_classes": [],
        "forbidden_tool_names": [],
        "schema_inventory_state": "NOT_AVAILABLE_FROM_TOOLS_COMMAND",
        "raw_output_committed": False,
        "mcp_authenticated": False,
        "mcp_server_started": False,
        "broker_request_count": 0,
        "sdk_called": False,
        "fixture_admitted": False,
        "execution_authority": False,
    }


def inspect_inventory(
    *,
    env: Optional[Mapping[str, str]] = None,
    process_runner: Callable[..., ProcessOutcome] = _run_process,
    temp_parent: Path = Path("/tmp"),
    temp_dir_factory: Callable[..., str] = tempfile.mkdtemp,
    chmod_func: Callable[[object, int], None] = os.chmod,
    cleanup_func: Callable[[object], None] = shutil.rmtree,
    receipt_writer: Callable[..., dict] = _write_and_verify_receipt,
    fsync_func: Callable[[int], None] = os.fsync,
    replace_func: Callable[[object, object], None] = os.replace,
    read_text_func: Callable[[Path], str] = _default_read_text,
    timeout: float = 30,
    grace_period: float = 1,
) -> dict:
    """Return a controlled, value-free result for every operational path."""
    process_env = dict(os.environ if env is None else env)
    presence = {name: bool(process_env.get(name)) for name in REQUIRED_ENVIRONMENT}
    result = _base_result(presence)

    if not all(presence.values()) or process_env.get("WEBULL_TOOLSETS") != "market-data":
        result["failure_class"] = FAILURE_OUTPUT_PARSE
        result["forbidden_classes"] = ["toolset_configuration"]
        result["verdict"] = "TOOLSET_CONFIGURATION_FAILED"
        return result

    original_umask = os.umask(0o077)
    chamber: Optional[Path] = None
    primary_failure = FAILURE_NONE
    verified_receipt: Optional[dict] = None

    try:
        try:
            chamber = Path(
                temp_dir_factory(prefix="selfbull-004b-mcp-inventory.", dir=str(temp_parent))
            )
            chmod_func(chamber, 0o700)
            stdout_path = chamber / "tools.stdout"
            stderr_path = chamber / "tools.stderr"
            pending_path = chamber / "inventory.pending.json"
            verified_path = chamber / "inventory.verified.json"

            with stdout_path.open("wb") as stdout_file, stderr_path.open("wb") as stderr_file:
                chmod_func(stdout_path, 0o600)
                chmod_func(stderr_path, 0o600)
                try:
                    outcome = process_runner(
                        INVENTORY_COMMAND,
                        env=process_env,
                        stdout=stdout_file,
                        stderr=stderr_file,
                        timeout=timeout,
                        grace_period=grace_period,
                    )
                except subprocess.TimeoutExpired:
                    primary_failure = FAILURE_PROCESS_TIMEOUT
                    result["status"] = STATUS_TIMEOUT
                    outcome = None
                except _ProcessGroupTerminationError:
                    primary_failure = FAILURE_PROCESS_TIMEOUT
                    result["status"] = STATUS_TIMEOUT
                    outcome = None
                except (PermissionError, OSError):
                    primary_failure = FAILURE_PROCESS_SPAWN
                    outcome = None
                except Exception:
                    primary_failure = FAILURE_UNEXPECTED
                    outcome = None

            if outcome is not None and outcome.timed_out:
                primary_failure = FAILURE_PROCESS_TIMEOUT
                result["status"] = STATUS_TIMEOUT
            elif outcome is not None:
                result["command_exit_code"] = outcome.returncode
                try:
                    stdout_text = _decode(stdout_path.read_bytes())
                    stderr_text = _decode(stderr_path.read_bytes())
                    combined = stdout_text + "\n" + stderr_text
                    if outcome.returncode != 0:
                        if _SECRET_VALUE_RE.search(combined):
                            raise InventorySafetyError("credential-like value detected")
                        raise InventoryParseError("inventory command failed")
                    receipt = parse_inventory_output(combined)
                except InventoryBoundaryError as exc:
                    primary_failure = FAILURE_OUTPUT_PARSE
                    result["forbidden_classes"] = list(exc.forbidden_classes)
                    result["forbidden_tool_names"] = list(exc.forbidden_tool_names)
                    result["verdict"] = "TOOLSET_CONFIGURATION_FAILED"
                except (InventoryParseError, InventorySafetyError, OSError):
                    primary_failure = FAILURE_OUTPUT_PARSE
                except Exception:
                    primary_failure = FAILURE_UNEXPECTED
                else:
                    try:
                        verified_receipt = receipt_writer(
                            receipt,
                            pending_path,
                            verified_path,
                            fsync_func=fsync_func,
                            replace_func=replace_func,
                            read_text_func=read_text_func,
                        )
                    except _ReceiptWriteError:
                        primary_failure = FAILURE_RECEIPT_WRITE
                    except _ReceiptVerifyError:
                        primary_failure = FAILURE_RECEIPT_VERIFY
                    except OSError:
                        primary_failure = FAILURE_RECEIPT_WRITE
                    except Exception:
                        primary_failure = FAILURE_UNEXPECTED
        except (PermissionError, OSError):
            if primary_failure == FAILURE_NONE:
                primary_failure = FAILURE_UNEXPECTED
        except Exception:
            if primary_failure == FAILURE_NONE:
                primary_failure = FAILURE_UNEXPECTED
    finally:
        cleanup_failed = False
        try:
            if chamber is not None:
                cleanup_func(chamber)
        except Exception:
            cleanup_failed = True
        finally:
            os.umask(original_umask)

        if chamber is not None:
            try:
                result["ephemeral_removed"] = not chamber.exists()
            except Exception:
                result["ephemeral_removed"] = False
        if cleanup_failed or not result["ephemeral_removed"]:
            result["cleanup_status"] = CLEANUP_FAILED
            result["cleanup_failure_class"] = FAILURE_CLEANUP
            if primary_failure == FAILURE_NONE:
                primary_failure = FAILURE_CLEANUP

    if primary_failure == FAILURE_NONE and verified_receipt is not None:
        result.update(verified_receipt)
        result["status"] = STATUS_COMPLETED
        result["failure_class"] = FAILURE_NONE
        result["atomic_receipt_verified"] = True
        result["verdict"] = "MCP_INVENTORY_WITNESSED"
    else:
        result["failure_class"] = primary_failure or FAILURE_UNEXPECTED
        if result["status"] != STATUS_TIMEOUT:
            result["status"] = STATUS_FAILED
        result.setdefault("verdict", "FAILED")
    return result


def main() -> int:
    try:
        report = inspect_inventory()
    except Exception:
        report = _base_result({})
        report["status"] = STATUS_FAILED
        report["failure_class"] = FAILURE_UNEXPECTED
        report["verdict"] = "FAILED"
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("status") == STATUS_COMPLETED else 2


if __name__ == "__main__":
    raise SystemExit(main())
