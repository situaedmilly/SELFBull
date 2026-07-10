"""Tests for selfbull.manual_capture — SELFBULL-002 mobile intake CLI.

Network sockets are disabled for this whole module (setUpModule) so any
accidental network call inside the intake path fails loudly — proof that
manual capture is fully offline. Standard library only.

Run: python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import io
import json
import os
import re
import socket
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

REPO_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = REPO_ROOT / "src" / "selfbull"
sys.path.insert(0, str(REPO_ROOT / "src"))

from selfbull import manual_capture  # noqa: E402

EXAMPLE_CSV = REPO_ROOT / "data" / "examples" / "manual_frequency_capture.csv"
INVALID_FIXTURE_CSV = Path(__file__).parent / "fixtures" / "manual_frequency_capture_invalid.csv"

_real_socket = socket.socket
_real_create_connection = socket.create_connection


def _no_network(*_args, **_kwargs):
    raise AssertionError("network call attempted during manual-capture tests")


def setUpModule():
    socket.socket = _no_network                      # type: ignore[assignment]
    socket.create_connection = _no_network           # type: ignore[assignment]


def tearDownModule():
    socket.socket = _real_socket                     # type: ignore[assignment]
    socket.create_connection = _real_create_connection  # type: ignore[assignment]


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = manual_capture.main(argv)
    return code, out.getvalue(), err.getvalue()


class TestValidateCommand(unittest.TestCase):
    def test_committed_example_csv_validates(self):
        code, out, _ = run_cli(["validate", "--file", str(EXAMPLE_CSV)])
        self.assertEqual(code, 0, out)
        self.assertIn("valid: 4/4", out)

    def test_validate_json_output(self):
        code, out, _ = run_cli(["validate", "--file", str(EXAMPLE_CSV), "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(len(payload["results"]), 4)
        self.assertTrue(all(r["validation_status"] == "valid" for r in payload["results"]))

    def test_invalid_fixture_returns_nonzero(self):
        code, out, _ = run_cli(["validate", "--file", str(INVALID_FIXTURE_CSV)])
        self.assertEqual(code, 1, out)

    def test_missing_file_is_usage_error(self):
        code, _, err = run_cli(["validate", "--file", "/nonexistent/nope.csv"])
        self.assertEqual(code, 2)
        self.assertIn("not found", err)


class TestIngestCommand(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store_path = Path(self._tmp.name) / "observations.jsonl"

    def test_valid_ingest_appends_rows(self):
        code, out, _ = run_cli([
            "ingest", "--file", str(EXAMPLE_CSV), "--store-path", str(self.store_path),
        ])
        self.assertEqual(code, 0, out)
        lines = self.store_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 4)
        first = json.loads(lines[0])
        self.assertEqual(first["source"], "webull_browser_manual")
        self.assertEqual(first["evidence"]["capture_mode"], "MANUAL_BROWSER_OBSERVATION")

    def test_dry_run_writes_nothing(self):
        code, out, _ = run_cli([
            "ingest", "--file", str(EXAMPLE_CSV),
            "--store-path", str(self.store_path), "--dry-run",
        ])
        self.assertEqual(code, 0, out)
        self.assertFalse(self.store_path.exists())
        self.assertIn("dry-run", out)

    def test_invalid_batch_writes_nothing(self):
        # The fixture holds one valid and one invalid row; a batch with any
        # invalid row must write zero rows.
        code, _, _ = run_cli([
            "ingest", "--file", str(INVALID_FIXTURE_CSV), "--store-path", str(self.store_path),
        ])
        self.assertEqual(code, 1)
        self.assertFalse(self.store_path.exists())

    def test_extra_csv_columns_fail_cleanly_and_write_nothing(self):
        bad_csv = Path(self._tmp.name) / "bad.csv"
        bad_csv.write_text(
            "timestamp_et,symbol,last_price,source,notes\n"
            "2026-07-10 09:35:00,SPY,632.14,webull_browser_manual,opening range,extra fragment\n",
            encoding="utf-8",
        )

        code, out, err = run_cli([
            "ingest", "--file", str(bad_csv), "--store-path", str(self.store_path),
        ])

        self.assertNotEqual(code, 0)
        self.assertIn("extra CSV columns detected beyond declared header", out + err)
        self.assertNotIn("Traceback", out + err)
        self.assertFalse(self.store_path.exists())

    def test_repeated_ingest_appends_without_rewriting(self):
        run_cli(["ingest", "--file", str(EXAMPLE_CSV), "--store-path", str(self.store_path)])
        first_lines = self.store_path.read_text(encoding="utf-8").splitlines()
        run_cli(["ingest", "--file", str(EXAMPLE_CSV), "--store-path", str(self.store_path)])
        lines = self.store_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 8)
        self.assertEqual(lines[:4], first_lines)


class TestSingleCommand(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store_path = Path(self._tmp.name) / "observations.jsonl"

    def test_single_valid_record_ingests(self):
        code, out, _ = run_cli([
            "single",
            "--timestamp-et", "2026-07-09 09:35:00",
            "--symbol", "SPY",
            "--last-price", "500.25",
            "--source", "webull_browser_manual",
            "--notes", "FICTIONAL test observation",
            "--store-path", str(self.store_path),
            "--json",
        ])
        self.assertEqual(code, 0, out)
        payload = json.loads(out)
        self.assertEqual(payload["results"][0]["validation_status"], "valid")
        self.assertIn("receipt", payload["results"][0])
        self.assertEqual(self.store_path.read_text(encoding="utf-8").count("\n"), 1)

    def test_single_validate_only_writes_nothing(self):
        code, _, _ = run_cli([
            "single",
            "--timestamp-et", "2026-07-09 09:35:00",
            "--symbol", "qqq",
            "--last-price", "430.80",
            "--source", "webull_browser_manual",
            "--validate-only",
            "--store-path", str(self.store_path),
        ])
        self.assertEqual(code, 0)
        self.assertFalse(self.store_path.exists())

    def test_single_invalid_record_fails_and_writes_nothing(self):
        code, _, _ = run_cli([
            "single",
            "--timestamp-et", "2026-07-09 09:35:00",
            "--symbol", "SPY",
            "--last-price", "-1",
            "--source", "webull_browser_manual",
            "--store-path", str(self.store_path),
        ])
        self.assertEqual(code, 1)
        self.assertFalse(self.store_path.exists())


class TestOfflineWitness(unittest.TestCase):
    """Static proof that the SELFBULL-002 intake modules stay offline and
    quarantined: no network client, no transport verb, no cross-repo import."""

    NEW_MODULES = ("manual_capture.py", "observation_parser.py", "observation_store.py")

    FORBIDDEN_PATTERNS = (
        r"\brequests\b", r"\bhttpx\b", r"\baiohttp\b",
        r"urllib\s*\.\s*request", r"^\s*import\s+socket", r"\bwebsocket",
        r"\bsubprocess\b", r"os\s*\.\s*system", r"\beval\s*\(", r"\bexec\s*\(",
        r"place_order", r"submit_order", r"cancel_order", r"replace_order",
        r"\btransfer\b", r"\bselfquant\b", r"\brbhcb\b",
        r"xoxb-", r"xapp-", r"app_secret", r"\bpassword\b", r"\btoken\b",
    )

    def test_intake_modules_contain_no_forbidden_surface(self):
        for name in self.NEW_MODULES:
            text = (SRC_DIR / name).read_text(encoding="utf-8")
            for pattern in self.FORBIDDEN_PATTERNS:
                self.assertIsNone(
                    re.search(pattern, text, re.MULTILINE),
                    f"forbidden pattern {pattern!r} found in {name}",
                )

    def test_intake_modules_do_not_import_selfquant_or_rbhcb(self):
        self.assertNotIn("selfquant", sys.modules)
        self.assertNotIn("rbhcb", sys.modules)

    def test_cli_output_never_dumps_environment(self):
        os.environ["SELFBULL_TEST_CANARY"] = "canary-value-must-not-leak-0123456789"
        try:
            code, out, err = run_cli(["validate", "--file", str(EXAMPLE_CSV)])
            self.assertEqual(code, 0)
            self.assertNotIn("canary-value-must-not-leak", out + err)
        finally:
            del os.environ["SELFBULL_TEST_CANARY"]

    def test_create_connection_teardown_restores_exact_original_object(self):
        self.assertIs(socket.create_connection, _no_network)
        tearDownModule()
        try:
            self.assertIs(socket.create_connection, _real_create_connection)
        finally:
            setUpModule()
        self.assertIs(socket.create_connection, _no_network)


if __name__ == "__main__":
    unittest.main()
