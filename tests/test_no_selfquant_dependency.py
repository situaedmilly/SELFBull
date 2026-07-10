"""Tests proving the interface-only boundary: SELFBull imports nothing from
SELFQUANT or RBHCB, ships no secret literal, and left SELFQUANT's protected
authority files byte-for-byte unchanged.

Standard library only. Run: python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = REPO_ROOT / "src" / "selfbull"
sys.path.insert(0, str(REPO_ROOT / "src"))

# Protected SELFQUANT files — hashes captured 2026-07-10 (Phase 0 witness),
# before any SELFBull work began. If SELFBull ever touched these, this
# fails. SELFQUANT-2026 is not a git repo, so this hash pin is the proof.
SELFQUANT_ROOT = Path.home() / "Projects" / "SELFQUANT-2026"
PROTECTED_HASHES = {
    "selfquant/adapters/adapter_contracts.py":
        "cfc401057354125c0e02b29ebf7a9854b6ce9f7da3867670a1544cc3bbc437a8",
    "selfquant/governors/agent_constitution.py":
        "a99bb63b3ca006d9babd902a5a4f23b39f2ecfb933245ecb6b1a8675248c24f0",
    "selfquant/schemas/trading_types.py":
        "6664d3246da28107d6e8f1b7b2ef5a85b53ded146cc44203abeaeb81212d56eb",
    "rbhcb/config.py":
        "a96aa678f5cd6fc3f57046512fce2caa20710c6bad1a24c64cea40a5099cba8a",
    "rbhcb/commands.py":
        "8d025cc6ca9cb5ec6f603bacd065d018a8fd251c504b58a32d38a334b7e25e25",
    "rbhcb/data_artery.py":
        "d2680fb393ea57da84f6bf09762c6c463c787a52aa4b4c6ac1df3b7869f46e83",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestNoSelfquantImport(unittest.TestCase):
    def test_package_imports_without_selfquant_on_path(self):
        # SELFQUANT-2026 is never added to sys.path by this test suite.
        self.assertFalse(any("SELFQUANT" in p for p in sys.path))
        import selfbull  # noqa: F401
        import selfbull.adapter  # noqa: F401
        import selfbull.contracts  # noqa: F401
        import selfbull.manifest  # noqa: F401
        import selfbull.audit  # noqa: F401
        self.assertNotIn("selfquant", sys.modules)
        self.assertNotIn("rbhcb", sys.modules)

    def test_no_source_file_imports_selfquant_or_rbhcb(self):
        import_pattern = re.compile(r'^\s*(from|import)\s+(selfquant|rbhcb)\b', re.MULTILINE)
        for path in sorted(SRC_DIR.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(
                import_pattern.search(text),
                f"{path} imports selfquant/rbhcb — interface-only boundary violated",
            )


class TestNoSecretLiterals(unittest.TestCase):
    def test_no_secret_literal_in_source(self):
        suspicious_markers = ("xoxb-", "xapp-", "sk-", "Bearer ", "-----BEGIN")
        env_default_pattern = re.compile(
            r'(app_key_id_env|app_key_secret_env)\s*:\s*str\s*=\s*"([^"]+)"'
        )
        for path in sorted(SRC_DIR.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for marker in suspicious_markers:
                self.assertNotIn(marker, text, f"{marker!r} found in {path}")
            for m in env_default_pattern.finditer(text):
                value = m.group(2)
                self.assertTrue(value.isupper(), f"non-uppercase default {value!r} in {path}")
                self.assertTrue(value.startswith("SELFBULL_"), f"unexpected default {value!r} in {path}")


class TestProtectedSelfquantHashesUnchanged(unittest.TestCase):
    def test_hashes_match_pre_selfbull_witness(self):
        if not SELFQUANT_ROOT.exists():
            self.skipTest("SELFQUANT-2026 not present on this machine — cannot cross-check")
        for rel_path, expected_hash in PROTECTED_HASHES.items():
            full_path = SELFQUANT_ROOT / rel_path
            self.assertTrue(full_path.exists(), f"protected file missing: {full_path}")
            actual = _sha256(full_path)
            self.assertEqual(
                actual, expected_hash,
                f"{rel_path} hash changed since the Phase 0 witness — "
                f"SELFQUANT authority files must remain untouched",
            )


if __name__ == "__main__":
    unittest.main()
