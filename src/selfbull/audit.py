"""selfbull.audit — redaction + audit-safe event log, Phase 1.

Standard library only. No import from selfquant or rbhcb — SELFBull keeps
its own, self-contained evidence plane, independent of SELFQUANT's.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_LOG_PATH = REPO_ROOT / "logs" / "selfbull_audit.jsonl"

_SECRET_KEYS = frozenset({
    "app_key_id", "app_key_secret", "app_key", "app_secret", "access_token",
    "refresh_token", "token", "token_type", "password", "passwd", "secret",
    "authorization", "bearer", "signature",
})


def redact(obj: Any) -> Any:
    """Recursively replace any secret-bearing value with a sentinel.
    Returns a new structure; never mutates the input."""
    if isinstance(obj, dict):
        return {
            k: ("«redacted»" if str(k).lower() in _SECRET_KEYS else redact(v))
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [redact(x) for x in obj]
    return obj


def log_event(entry: dict, path: Optional[Path] = None) -> None:
    """Append one redacted, execution_authority=False event to the JSONL
    evidence plane. Creates the target directory if absent."""
    target = path or AUDIT_LOG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    safe = redact(entry)
    safe.setdefault("execution_authority", False)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(safe) + "\n")
