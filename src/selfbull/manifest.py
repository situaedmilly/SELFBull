"""selfbull.manifest — SELFBULL-001 · broker manifest, Phase 1.

SELFBull is not a trading bot yet. SELFBull is a broker interface temple.
The hand does not execute until the crown authorizes.

Declares WHAT SELFBull is allowed and forbidden to do at the current phase,
and exposes a `status()` snapshot safe to print or log — it never contains
a credential value, only presence. No import from selfquant or rbhcb.
"""
from __future__ import annotations

from typing import Tuple

from selfbull.adapter import WebullAdapter, kill_switch_active

SELFBULL_PHASE = 1

PHASE1_ALLOWED_CAPABILITIES: Tuple[str, ...] = (
    "config shape validation",
    "credential presence check without printing values",
    "read-only account/market-data interface stubs (raise NotImplementedError, no network)",
    "paper/simulated order object creation",
    "audit-safe event records (secrets redacted)",
    "live-order refusal path",
    "tests proving live execution is unreachable",
)

PHASE1_FORBIDDEN_CAPABILITIES: Tuple[str, ...] = (
    "quote retrieval",
    "account retrieval",
    "login",
    "refresh-token handling",
    "order preview through Webull",
    "order placement",
    "cancellation",
    "replacement",
    "transfer",
    "autonomous decision-making",
    "background execution",
)


def status() -> dict:
    """A snapshot safe to print or log. Contains presence booleans and an
    at-most-4-char App Key ID preview — never a full credential value."""
    adapter = WebullAdapter()
    snapshot = adapter.build_capability_snapshot()
    return {
        "broker": "webull",
        "phase": SELFBULL_PHASE,
        "environment": snapshot.environment,
        "live_transport_available": snapshot.live_transport_available,
        "live_transport_enabled": snapshot.live_transport_enabled,
        "kill_switch_active": kill_switch_active(),
        "credential_state": snapshot.credential_state,
        "allowed_capabilities": list(PHASE1_ALLOWED_CAPABILITIES),
        "forbidden_capabilities": list(PHASE1_FORBIDDEN_CAPABILITIES),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(status(), indent=2))
